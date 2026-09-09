# Hot Design x Design Graph: integration findings

Read-only study of `unoplatform/uno.hotdesign` at `7447bc5` (main) against this plugin at
`ba434e3`. Paths without a prefix are in `uno.hotdesign`. Line numbers are from that commit.
Nothing in `uno.hotdesign` was modified.

Sources outside the two repos, read because the snapshot producer lives in neither:

- `unoplatform/uno` (public, shallow sparse clone): `src/Uno.UI/Diagnostics/ElementRefHandle.cs`,
  `src/Uno.UI.RemoteControl/Tools/*.cs`, `specs/042-element-ref-registry/spec.md`,
  `specs/044-tool-registry/spec.md`.
- NuGet `Uno.UI.App.Mcp` **1.3.4** (`tools/devserver/Uno.UI.App.Mcp.Server.dll`,
  `lib/net9.0/Uno.UI.App.Mcp.Client.dll`): the `uno_app_visualtree_snapshot` tool description and
  the renderer's type/field names, extracted as strings. The repo pins **1.3.2**
  (`src/Directory.Packages.props:14`), which is not on nuget.org (the version index jumps from
  `1.3.0-dev.112` to `1.3.3`), so 1.3.4 is the closest readable build.

## 1. Elements panel model

### Evidence

View model and node types (assembly `Uno.UI.HotDesign.Hierarchy`):

- `src/Uno.UI.HotDesign.Hierarchy/HierarchyViewModel.cs:22-24` — `HierarchyViewModel : BaseToolWindowViewModel`,
  `Tool => Tools.Elements`. `:412` `Root` (a `NodeViewModel`), `:408` `SelectedItems`,
  `:53` `SelectionChanged`, `:59` `HierarchyRebuilt`, `:429-430` `Refresh()` sends
  `HierarchyRequestMessage`, `:545-577` `UpdateHierarchy(HierarchyItem? root)` rebuilds or diffs the tree.
- `src/Uno.UI.HotDesign.Hierarchy/NodeViewModel.cs:10-16` — abstract node; `:42` wraps one
  `HierarchyItem`; `:44-46` `ElementIdentifierWithPath` / `ElementIdentifier`; `:106-107`
  `ElementType` resolved from the fully-qualified name; `:109` `Name => HierarchyItem.DisplayName`;
  `:111-120` children built from `HierarchyItem.Children`; `:82-88` `DisplayNamePrefix/Match/Suffix`
  (search highlight split of the label).
- `src/Uno.UI.HotDesign.Hierarchy/ElementNodeViewModel.cs:7-8`, `PropertyNodeViewModel.cs` — the two concrete kinds.

The DTO behind every node (assembly `Uno.UI.HotDesign.Messaging`):

- `src/Uno.UI.HotDesign.Messaging/Models/HierarchyItem.cs:9-36` — `HierarchyItem(ItemType, IsReadOnly,
  IsSelected, IsSelectable, IsInTemplate, IsCollapsed, ElementIdentifierWithPath?, ElementName?,
  PropertyName?, DropTargetType, CanEditAsUserControl, HasDesignTimeData, SupportedTypes?, Children?)`.
  `:41-54` `DisplayName` = `[ElementTypeName] ElementName`.
- `src/Uno.UI.HotDesign.Abstractions/ElementIdentifier.cs:20-27, 56-71` — `FileName`, `SourceLine`,
  `LinePosition`, `ElementTypeName` (short name derived at `:65`), `ElementTypeFullyQualifiedName`
  (assembly-qualified, `:67`), `ShadowIdentifier` (`:69`, Hot Design-inserted elements), `HashCode`.
  `:223-232` `IsValid`, `:242-245` `IsEditable`.

Where the fields come from (assembly `Uno.UI.HotDesign.Client`):

- `src/Uno.UI.HotDesign.Client/Logic/HierarchyLogic.cs:520-525` — `elementName = element.Name` (the runtime
  `FrameworkElement.Name`, i.e. `x:Name`); `:602-604` falls back to the type name when unnamed **and**
  the identifier is invalid; `:527` `element.ToElementIdentifier()`; `:634-661` the `ElementHierarchyItem`
  constructor call that fills every `HierarchyItem` field.
- `src/Uno.UI.HotDesign.Client.Core/Extensions/DependencyObjectExtensions.cs:25-107` — identity precedence:
  shadow details (`:56-72`), `FrameworkElement.GetDebugParseContext()` file/line/column (`:75-83`),
  `OriginalSourceLocation` (`:87-93`), hash-code-only for code-behind elements (`:97-107`).
- Style key and DataContext type are **not** on the tree node. They reach the Properties panel by a
  different path: `src/Uno.UI.HotDesign.Client/AppUpdater.Xaml.cs:62-69` reads the element's own XAML
  from the shadow DOM; `src/Uno.UI.HotDesign.Client/Logic/ObjectDetailsLogic.cs:241, 537` turn
  attributes into `PropertyDetails`; a `Style="{StaticResource X}"` becomes
  `src/Uno.UI.HotDesign.Messaging/Models/Values/ResourcePropertyValue.cs:6-37` (`ResourceType`
  = StaticResource/ThemeResource, `ResourceName` = the key). DataContext type:
  `ObjectDetailsLogic.cs:881, 1245-1247` (`fe.DataContext.GetType()`).

Row template:

- `src/Uno.UI.HotDesign.Hierarchy/HierarchyView.xaml:561` `PART_Tree`; `:578-590` item template
  (`TreeViewItem Content="{Binding}"`, `ItemsSource="{Binding Children}"`); `:762-763` `RootNodeLabel`
  grid (`Auto,*`); `:792-803` `NodeLabel` TextBlock with three `Run`s bound to
  `DisplayNamePrefix/Match/Suffix`. Spec: `specs/hierarchy/spec.md:787-796` (tree is a template over
  a view model), `:1074-1097` (label rule), `:1422-1440` (four-layer table).

### Field map

| `uno.*` key | Elements node counterpart | Where |
|---|---|---|
| `type` | `ElementIdentifier.ElementTypeName` | `Abstractions/ElementIdentifier.cs:65` |
| `namespace` | namespace part of `ElementTypeFullyQualifiedName` | `Abstractions/ElementIdentifier.cs:67` |
| `class` (screen/component) | `ElementTypeFullyQualifiedName` of the Page/UserControl node | same |
| `xName` | `HierarchyItem.ElementName` (from `FrameworkElement.Name`) | `Client/Logic/HierarchyLogic.cs:520` |
| source file / line / column | `ElementIdentifier.FileName/SourceLine/LinePosition`, or `ShadowIdentifier` | `Abstractions/ElementIdentifier.cs:56-69` |
| `styleKey` | **none on the node**; available per selected element via shadow XAML | `Client/AppUpdater.Xaml.cs:62`, `Messaging/Models/Values/ResourcePropertyValue.cs:12` |
| `resourceKey`, `resourceType` (token) | **none per element**; `ResourceDetails` exists only for the resource picker | `Messaging/Models/ResourceDetails.cs:9` |
| `mechanism`, `member`, `visualState` (state) | **none** | not found |
| DataContext type | **none on the node**; Properties panel only | `Client/Logic/ObjectDetailsLogic.cs:881` |

Caveat on `xName`: `ElementName` equals the type name for unnamed code-behind elements
(`HierarchyLogic.cs:602-604`); disambiguate with `ElementIdentifier.IsValid`.

Hot Design-only fields with no graph key: `HashCode`, `ShadowIdentifier`, `IsInTemplate`, `IsReadOnly`,
`IsCollapsed`, `DropTargetType`, `CanEditAsUserControl`, `HasDesignTimeData`, `SupportedTypes`.

### Conclusion

`HierarchyItem` already carries `uno.type`, `uno.namespace`, `uno.class`, `uno.xName` and the source
location. An annotation that shows those needs no data-source change: one computed property on
`NodeViewModel` (from `HierarchyItem`) and one extra `Run` or column in `HierarchyView.xaml:792-803`.
`styleKey`, `resourceKey`, states and DataContext type are not on the tree; adding `styleKey` means a new
`HierarchyItem` field populated in `HierarchyLogic.cs:634-661` from the shadow XAML, which `HierarchyLogic`
does not currently read (the reader is on `AppUpdater`).

## 2. Panel / tool registration

### Evidence

- Layout is hard-coded in the host template: `src/Uno.UI.HotDesign.Client/Controls/HotDesignClientHost.xaml:1290-1338`
  (`HierarchyRow`/`ToolboxRow`, `HierarchyContainer` hosting `hierarchy:HierarchyView`, `ToolboxContainer`
  hosting `htd:ToolboxView`, `PreviewsContainer` hosting `hdp:PreviewsView`), `:1374-1379`
  (`PropertyGridViewContainer` hosting `pg:PropertyGridView`). Visibility is visual states:
  `:529-586` `LeftSideToolStates` (`LeftSideToolsNone/ToolboxVisible/TreeVisible/ToolboxAndTreeVisible`),
  `:436-456` `RightSideToolStates`, `:128-137` `HotDesignActive` sets `Toolbox.IsActive` / `Hierarchy.IsActive`.
- Code-behind sizing: `HotDesignClientHost.xaml.cs:1016-1017` (template rows), `:1614-1637` row heights.
- Visibility model: `src/Uno.UI.HotDesign.Messaging/Models/VisiblePanel.cs:4-11` flags
  `Toolbox | Tree | Properties`; `src/Uno.UI.HotDesign.Client/HotDesignClientViewModel.cs:335, 433-460`
  (`ToolboxVisible`, `ElementsVisible`, `PropertiesVisible`, left/right composites), `:2200-2219` toggles,
  `:2327-2329` `ToolWindowResponseMessage(ToolboxVisible, ElementsVisible, PropertiesVisible)`;
  `src/Uno.UI.HotDesign.Messaging/Messages/ToolWindowRequestMessage.cs:5` (three booleans).
- Tool identity: `src/Uno.UI.HotDesign.Messaging/Messages/Tools.cs:7-` enum
  `None, Toolbox, Elements, Properties, Chat, Previews, TopBar, External`.
- The common panel abstraction is a base view model, not a registry:
  `src/Uno.UI.HotDesign.Client.Core/BaseToolWindowViewModel.cs:11` (`ObservableObject, IHotDesignMessageHandler`),
  `:15` `Tool`, `:40-49` `SupportedMessageNames`, `:58-67` `Tool -> InteractivityTarget`,
  `:317` `MessageBrokerRegistrar.Default.RegisterNested(this, isHostedTool)`, `:331`
  `ClientStateRequestMessage(Tool)`. Each view news up its own VM: `Hierarchy/HierarchyView.xaml.cs:82`,
  `Toolbox/ToolboxView.xaml.cs:25`, `PropertyGrid/PropertyGridView.xaml.cs:59`, `Previews/PreviewsView.xaml.cs:117`.
- Per-tool startup push is a switch on the enum: `src/Uno.UI.HotDesign.Client/HotDesignClientMessageHandler.cs:495-520`.
- Assemblies are wired by project reference, not discovery: `src/Uno.UI.HotDesign.Client/Uno.UI.HotDesign.Client.csproj:20-26`.
- External window mirrors the same fixed set: `src/Uno.UI.HotDesign.Windows/Presentation/MainPage.xaml:52-88`
  (`ToolboxStates`, `HierarchyStates`, `PropertyGridStates`); `MainViewModel.cs:12` `Tools.External`.
- No DI container, no panel registry: `rg "IPanel|PanelRegistry|RegisterPanel|AddPanel"` over `src/` finds nothing.
- Precedent for adding/removing a panel: `specs/chat/spec.md:51-66` (the Chat project, `ChatViewContainer`,
  its overlays and its `Tools.Chat` arm were removed in #7977; `Tools.Chat`/`InteractivityTarget.Chat` retained).
- Protocol spec: `specs/messaging/spec.md:1450-1509` (Tool Window Registration Protocol);
  public-surface rule `specs/architecture/spec.md:84-90` (everything internal).
- The one open extension point is MCP: `src/Uno.UI.HotDesign.Client/Logic/Abstractions/IToolResourcePublisher.cs:10-37`
  (`Register(uri, ..., Func<string> jsonBody)`, `RegisterTool(name, ..., handler)`), adapter
  `Logic/Mcp/ToolRegistryResourcePublisher.cs:18-96` over Uno's `ToolRegistry.Publisher`
  (`unoplatform/uno src/Uno.UI.RemoteControl/Tools/ToolRegistry.cs:14-22`), wired in
  `Logic/Hosting/HostingService.cs:252-287`, resources listed in `Logic/Mcp/HotDesignToolPublisher.cs:37-44`.

### Conclusion

**(b) a small host change, but multi-file.** A fourth in-app pane follows an existing pattern
(`BaseToolWindowViewModel` + broker registration), yet every hosting site is enumerated by hand. The
files a pane touches: `HotDesignClientHost.xaml` (container + `LeftSideToolStates`), `HotDesignClientHost.xaml.cs`
(row sizing), `HotDesignClientViewModel.cs` (`VisiblePanels` composites and toggle), `VisiblePanel.cs`,
`Tools.cs`, `ToolWindowRequestMessage.cs`/`ToolWindowResponseMessage.cs`, `HotDesignClientMessageHandler.cs:495`
(startup push), `Windows/Presentation/MainPage.xaml`, `Client.csproj`, plus a new project for the view.
Rendering a node graph in XAML is the genuinely new part (no graph control exists in the repo). The
graph does not need a pane to be useful: the MCP registry is an extension point that already crosses
the DevServer to any agent, and the browser inspector already exists.

## 3. Visual tree snapshot format

### Evidence

- `uno_app_visualtree_snapshot` is **not produced in `uno.hotdesign`**: `rg -i visualtree_snapshot src/`
  matches nothing; only skill docs mention it (`.claude/skills/uno-app-launch/SKILL.md:62`,
  `.claude/skills/launch-hd-desktop/SKILL.md:142`). It ships in NuGet `Uno.UI.App.Mcp`
  (`src/Directory.Packages.props:14`, `devserver-addins/DevServerAddIns.csproj`), whose source is not
  in `unoplatform/uno` either (that clone holds only the registry and `ElementRefHandle`).
- **Not the same producer as the Elements tree.** Hot Design's tree is `HierarchyLogic.CreateHierarchy`
  (`Client/Logic/HierarchyLogic.cs:112`) walking XAML content/collection properties through
  `FindDirectChildrenByDescriptor` (`:692`), stopping at `UserControl` boundaries (`:541`) and
  flattening content-property nodes (`:592-594`); it is serialized as `HierarchyResponseMessage(Root,
  ScopeRoot, CurrentScopeId)` (`Messaging/Messages/HierarchyResponseMessage.cs:6`) via source-generated
  System.Text.Json contexts (`Messaging/Serializer.cs:17-`; `ElementIdentifier` has a custom converter,
  `Serializer.cs:13`). The App MCP renderer walks `VisualTreeHelper` (client DLL strings `BuildVisualTree`,
  `VisualTreeHelper`, `Uno.UI.App.Mcp.Client.VisualTree`, `VisualTreeTextRenderer`) and includes template
  internals as `lib:` nodes. Both derive file/line from the same Uno member: `FrameworkElement.DebugParseContext`
  (`DependencyObjectExtensions.cs:77`; client DLL string "Visual tree source locations unavailable:
  FrameworkElement.DebugParseContext could not be resolved (Release build ...)").
- **Format, pinned from the tool description in `Uno.UI.App.Mcp.Server.dll` 1.3.4** (parameters:
  `detail` = compact | normal | full, `includeHidden`, `elementRef`; renderer node fields: `Ref, TypeName,
  Origin, Source{File,Line,Column}, ScopeKind, Name, Text, AutomationPatterns, Bindings, DataContextType,
  Flags, Opacity, Bounds, Children`). Text outline, one element per line, 2-space indent = nesting:

  | token | meaning |
  |---|---|
  | `@ File ^N (Kind, dc:VM)` | opens a source-file scope; Kind = Page/UserControl/...; `(...)` omitted when unknown |
  | `Type ^N` / `lib:Type ^N` | type name and ref handle (bare token after `^`); `lib:` = framework type |
  | `#Name` | `x:Name` **or** `AutomationProperties.Name` |
  | `:L` / `:L:C` | source line[:column] relative to the enclosing `@ File` |
  | `"text"` | text content |
  | `[i t x s v r c]` | automation patterns (detail=normal+) |
  | `Prop={Path}`, `{Path,1way|2way|1time}`, `{Path|conv}` | classic `{Binding}`; x:Bind is not detectable |
  | `dc:Type` | locally-set DataContext runtime type |
  | `o:.5`, `xf` | opacity, RenderTransform present |
  | `@@x,y,w,h` | arranged bounds relative to the snapshot root (detail=full) |
  | `!hidden`, `!offscreen`, `!code`, `!lib` | flags; editable iff `:line` under a `@` scope |

  The producer's own example (verbatim from the description string):

  ```text
  @ Views/MainPage.xaml ^0  (Page, dc:MainVM)
    Grid ^1 :3
      TextBlock ^4 :7  "Welcome"
      Button ^5 #Save :9 [i]  "Save" IsEnabled={CanSave}
      lib:ProgressRing ^6  !lib
  ```

- Hot Design's own tree on the wire (reconstructed from `HierarchyItem.cs:9-36`, `ElementIdentifierWithPath.cs:9`,
  `ElementSelectionPath.cs:7-10`; defaults are omitted by `JsonIgnore(WhenWritingDefault)`):

  ```json
  {"Root": {"ElementIdentifierWithPath": {"Id": {"FileName": "Presentation/SettingsPage.xaml", "SourceLine": 12,
    "LinePosition": 3, "ElementTypeFullyQualifiedName": "Microsoft.UI.Xaml.Controls.Grid, Uno.UI, ...",
    "ShadowIdentifier": "", "HashCode": 1234, "HasHashCode": true}, "Path": []},
    "ElementName": null, "PropertyName": {"Name": "Children"}, "DropTargetType": 2,
    "Children": [ {"ElementIdentifierWithPath": {...}, "ElementName": "SaveUsernameButton"} ]},
   "ScopeRoot": {...}, "CurrentScopeId": null}
  ```

### Sufficiency

| `uno.*` | snapshot | Hot Design tree |
|---|---|---|
| `type` | yes (`Type`, `lib:` stripped) | yes (`ElementTypeName`) |
| `xName` | yes, but conflated with `AutomationProperties.Name` | yes (`ElementName`, see caveat) |
| `namespace` | no (`lib:` flag only) | yes (from FQN) |
| `class` | no (`@ File (Kind)` only) | yes (FQN of the Page/UserControl) |
| `styleKey` | **no** | no on the node; yes via shadow XAML |
| `resourceKey` | **no** | no |
| source file/line | yes | yes, plus `ShadowIdentifier` for designer-inserted elements |
| DataContext type | yes (`dc:`) | no on the node |

So the snapshot is sufficient for `uno.type` and `uno.xName`, and for the `contains` tree. It cannot
supply `uno.styleKey`, `uno.resourceKey`, `uno.class` or `uno.namespace`; those have to come from Hot
Design (the shadow XAML for style keys, `ElementTypeFullyQualifiedName` for class/namespace).

### Conclusion

A mechanical parser is worth having and is written (section "Snapshot parser"). The round-trip
contract on `styleKey`/`resourceKey` stays a Hot Design job; the snapshot alone will always report
them as drift.

## 4. Selection sync

### Evidence

Canvas to Elements:

- `src/Uno.UI.HotDesign.Client/Controls/DesignerOverlay.xaml.cs:1005-1011` `SelectElement` ->
  `ViewModel.AppInfoProvider.SelectElement(element, replaceAllSelection)`.
- `src/Uno.UI.HotDesign.Client/Controls/HotDesignClientHost.xaml.cs:1894-1905` `SelectElement` ->
  `AddToSelection` (`:443-451`) -> `OnSelectionChanged` (`:1881-1891`): raises
  `SelectedElementsCollectionChanged`, sends `SelectedElementsRequestMessage`, updates `SelectionService`.
- `src/Uno.UI.HotDesign.Client/HotDesignClientMessageHandler.cs:936-948` answers with
  `SelectedElementsResponseMessage(ElementIdentifierWithRef[])`.
- `src/Uno.UI.HotDesign.Hierarchy/HierarchyViewModel.cs:506-508, 609-628, 630-669` applies it to the tree.

Elements to canvas:

- `HierarchyViewModel.cs:432-467` `SetItemsSelection` -> `SelectElementsMessage`
  (`src/Uno.UI.HotDesign.Messaging/Messages/SelectElementsMessage.cs:10`).
- `HotDesignClientMessageHandler.cs:282-283, 1099-1100` -> `IAppInfoProvider.UpdateSelectedElements`
  (`HotDesignClientHost.xaml.cs:395-441`): resolves each `ElementIdentifier` with `AppUpdater.TryGetElement`
  (`:391-393`), then `AddToSelection`, which loops back through the response above.

Reachable from outside the panel:

- In-process event: `src/Uno.UI.HotDesign.Client.Core/IAppInfoProvider.cs:34`
  `SelectedElementsCollectionChanged`, consumed by `Adorners/AdornersLayer.cs:80` and `Rulers/CanvasRulersLayer.cs:532`.
- Message bus: any `IHotDesignMessageHandler` registered through `MessageBrokerRegistrar`
  (`BaseToolWindowViewModel.cs:317`) can send `SelectElementsMessage` and receive
  `SelectedElementsResponseMessage`; the external tool window does exactly that over the DevServer
  (`Client/Logic/DevServer/RemoteControlService.cs:157-158`, `ForwardedMessage`; `specs/architecture/spec.md:73-82`).
- MCP: **no selection resource or tool today.** Resources are mode/connectivity/theme/form-factors/form-factor/
  app-mode/previews/preview (`Logic/Mcp/HotDesignToolPublisher.cs:37-44`); tools are set_mode/set_theme/
  set_form_factor/set_app_mode/select_preview/create_preview/delete_preview/screenshot_preview
  (`Logic/Hosting/HostingService.cs:252-287`). Per-element operations are explicitly deferred
  (`specs/mcp-tools/spec.md:1496`).
- The join key already exists: `SelectedElementsResponseMessage` carries `UnoElementRef`
  (`Messaging/Models/ElementIdentifierWithRef.cs:9-14`), populated by `Uno.UI.Diagnostics.ElementRefHandle.GetOrCreate`
  (`Client/Extensions/FrameworkElementExtensions.cs:103-124`; `specs/messaging/spec.md:1072-1120`).
  That handle is the same base-36 token the snapshot prints after `^`
  (`unoplatform/uno src/Uno.UI/Diagnostics/ElementRefHandle.cs:53, 73`; spec 042).

### Conclusion

Selection-as-context already exists on the Hot Design message bus: `SelectedElementsResponseMessage`
carries the App MCP handle for each selected element, and `SelectElementsMessage` selects from outside
the panel. The ElementRef bridge was built so that "an agent receiving a Hot Design selection" can
target the element in App MCP tools (`specs/messaging/spec.md:1080`); the Studio Live host, which
supplies the Agent experience in nested mode (`specs/chat/spec.md:107-111`), sits on that bus. Its
consumer is outside this repo: `git log -S unoRef -- src` finds nothing, and the
`agent-mode-element-selection` spec the bridge cites is no longer in `specs/chat/`.

What is missing is only the **MCP republication** of that bus traffic, for an agent that is not
Studio Live. "Click a node in the graph inspector, highlight it in Hot Design" is therefore a **new,
small MCP tool**, not a new subsystem: `hotdesign_select_element(element_ref)` resolving `ElementRefHandle.TryResolve` and calling
`IAppInfoProvider.SelectElement`. The reverse direction is a `hotdesign://selection` resource fed from
`SelectedElementsCollectionChanged`. Until those exist, the only external paths are the in-process event
and the Hot Design message bus, neither of which a browser page can reach; an agent sitting between the
inspector and the App MCP can, once the tool exists.

## Smallest viable integration

Three steps, ordered by what they buy; the first needs no Hot Design change.

1. **Plugin side, no Hot Design change.** `snapshot_to_graph.py` (below) turns
   `uno_app_visualtree_snapshot` into a runtime graph; `diff_graph.py` then reports drift on `type`/`xName`
   and shows `styleKey`/`class` as gaps. `runtime-source.md` step 3 becomes mechanical.

2. **Selection bridge over MCP (3-4 files in `uno.hotdesign`).** Republishes the selection the bus
   already carries so a non-Studio-Live agent can read and drive it: the inspector highlights what Hot
   Design selects and vice versa. Skip this step if the consuming agent is Studio Live's own.
   - new `src/Uno.UI.HotDesign.Client/Logic/Mcp/HotDesignSelectElementTool.cs` (shape of
     `HotDesignSelectPreviewTool.cs:18-25`);
   - new `Logic/Mcp/SelectionController.cs` reading `IAppInfoProvider.CurrentSelection` and
     `SelectedElementsCollectionChanged` through a `Func<IAppInfoProvider?>` like
     `HostingService.cs:63` does for the catalogue;
   - `Logic/Mcp/HotDesignToolPublisher.cs` (+`hotdesign://selection` resource, +tool registration) and
     `Logic/Hosting/HostingService.cs:252-287` (wire);
   - `specs/mcp-tools/spec.md` (Requirements scenarios + Implementation), tests in
     `Tests/Uno.UI.HotDesign.Client.Tests/` next to the existing tool tests.

   Patch sketch (not a commit):

   ```csharp
   // Logic/Mcp/HotDesignSelectElementTool.cs
   internal sealed class HotDesignSelectElementTool
   {
       public const string ToolName = "hotdesign_select_element";
       public const string ElementRefParameter = "element_ref";
       private readonly Func<IAppInfoProvider?> _host;
       private readonly Func<Func<Task>, Task> _runOnUiThread;

       public HotDesignSelectElementTool(Func<IAppInfoProvider?> host, Func<Func<Task>, Task> runOnUiThread)
           => (_host, _runOnUiThread) = (host, runOnUiThread);

       public IReadOnlyList<ToolParameterInfo> Parameters { get; } =
           [new ToolParameterInfo(ElementRefParameter, "Handle from uno_app_visualtree_snapshot (bare token after '^').", IsRequired: true)];

       public async ValueTask<ToolOutcome> InvokeAsync(IReadOnlyDictionary<string, string> arguments, CancellationToken ct)
       {
           if (!arguments.TryGetValue(ElementRefParameter, out var handle) || string.IsNullOrWhiteSpace(handle))
           {
               return ToolOutcome.Error("element_ref is required.");
           }
           var host = _host();
           if (host is null)
           {
               return ToolOutcome.Error("Hot Design is not showing an app.");
           }
           var selected = false;
           await _runOnUiThread(() =>
           {
               if (Uno.UI.Diagnostics.ElementRefHandle.TryResolve(handle.TrimStart('^'), out var element)
                   && element is FrameworkElement fe)
               {
                   host.SelectElement(fe);
                   selected = true;
               }
               return Task.CompletedTask;
           });
           return selected ? ToolOutcome.Success($"Selected ^{handle}.") : ToolOutcome.Error($"No live element for '{handle}'; take a fresh snapshot.");
       }
   }
   ```

   `hotdesign://selection` JSON body (one entry per `ElementIdentifierWithRef`, same fields the panel gets):

   ```json
   {"elements": [{"element_ref": "b", "type": "Button", "type_fqn": "Microsoft.UI.Xaml.Controls.Button, ...",
                  "x_name": "SaveUsernameButton", "file": "Presentation/SettingsPage.xaml", "line": 31, "column": 5}]}
   ```

   `NotifyUpdated()` on `SelectedElementsCollectionChanged`, deduplicated like the theme snapshot
   (`HotDesignToolPublisher.cs:23-34`).

3. **Optional: graph identity on the Elements row (2 files).** Add to `NodeViewModel.cs` a computed
   `GraphIdentity` string built from `HierarchyItem` (`{type} #{xName} {file}:{line}`; nothing new on the
   wire) and a fourth `Run` in `HierarchyView.xaml:792-803` styled like `DisplayNameMatch`. `styleKey`
   is out of reach here without extending `HierarchyItem` and `HierarchyLogic.cs:634-661`, which is the
   first change that would touch the data source.

A dedicated graph pane inside Hot Design is deliberately not in this list: it costs the file set in
section 2 plus a XAML node-graph control, and buys nothing the browser inspector plus the MCP bridge
does not already give.

## Snapshot parser

Written in this clone, uncommitted:

- `skills/uno-design-graph/scripts/snapshot_to_graph.py` (stdlib only; `--include-lib`, `--screen-slug`,
  `--graph-id`, `--design <graph>`; exit 1 on empty input).
- `skills/uno-design-graph/scripts/tests/fixtures/orbital-settings.reconstructed.snapshot.txt` —
  **reconstructed** from the 1.3.4 line grammar and the identities in `examples/orbital-settings.graph.json`;
  not a capture from a running app.
- `skills/uno-design-graph/scripts/tests/test_snapshot_to_graph.py` (17 tests: parsing, flags, bindings,
  bounds, non-identifier `#Name`, both nested-UserControl line shapes, id grammar, schema + strict lint,
  diff expectations, CLI).

Mapping rules: `@ File (Kind)` root -> `screen` (`uno.type` = Kind); nested `@` scope -> `component`
(`uno.type` = Kind); element type -> `control` / `content` / `asset` / `region` by a type table, else
`region` when it has children; `uno.xName` only when `#Name` is a XAML identifier (otherwise
`properties.automationName`); `!lib` nodes dropped by default; `!hidden`/`!code`/`!offscreen` become
`tags`; `dc:` -> `properties.dataContextType`; `Prop={...}` -> `properties.bindings`; `@@` -> `geometry`;
every node is `observed` / `runtime` with `evidence.locator = {ref, file, line, column, flags}`.
Ids are `<type>.<screen>.<xname-slug | type-line | type-ref>` so they are stable across sessions when
a name or source line exists. `--design` adopts the design graph's node **type and id** for x:Names the
runtime confirms and never copies `uno.*` from it; it exists because `diff_graph.py` keys identity on
`(node type, xName)`, so a `region` in the runtime graph and a `component` in the design graph with the
same `xName` would otherwise read as missing + extra.

Test run (`python3 -m unittest discover -s skills/uno-design-graph/scripts/tests`):

```text
Ran 42 tests in 0.859s
OK
```

`diff_graph.py examples/orbital-settings.graph.json <generated>` (mechanical run, no `--design`):

```text
DRIFT: 10 missing, 3 changed, 18 extra
  - missing  asset.header.logo  (id=asset.header.logo)
  - missing  control.header.search  (id=control.header.search)
  - missing  component.settings-card  (id=component.settings-card)
  - missing  component.settings-card.profile  (xName=ProfileSection)
  - missing  content.about.section-title  (id=content.about.section-title)
  - missing  component.info-row  (id=component.info-row)
  - missing  state.profile.saved  (id=state.profile.saved)
  - missing  state.settings.entering  (id=state.settings.entering)
  - missing  token.radius.12  (id=token.radius.12)
  - missing  token.color.surface1  (resourceKey=OrbitalSurface1Brush)
  ~ changed  control.profile.save  uno.styleKey: 'OrbitalPrimaryButtonSm' -> None
  ~ changed  screen.settings  uno.class: 'Orbital.Presentation.SettingsPage' -> None
  ~ changed  component.page-header  uno.class: 'Orbital.Controls.PageHeader' -> None
  + extra    region.settings.grid-12  (id=region.settings.grid-12)
  ... 17 more unnamed runtime nodes
```

Reading it: `UsernameBox` and `SaveUsernameButton` match on `xName`; the three `changed` rows are exactly
the keys the snapshot cannot carry (`styleKey`, `class`); the `missing` states and tokens are the design
layers a runtime tree never has; with `--design` the `ProfileSection` card matches too (9 missing).
`asset.header.logo` and `control.header.search` are unnamed design nodes with no locator, so nothing
in a runtime graph can claim them; that is a gap in the example graph as much as in the parser.

## Unresolved Questions

- The nested `@ File ^N (UserControl)` line shape is reconstructed. The parser accepts both a lone
  scope line and a `Type ^N` line followed by `@ File ^N` with the same handle (folded into one node),
  so either shape produces the same graph; a live capture is still wanted as a second fixture:
  launch `Samples/MvvmMaterialFrame` per `launch-hd-desktop`, call
  `uno_app_visualtree_snapshot({detail:"full", includeHidden:true})`, and paste the output.
- `#Name` cannot distinguish `x:Name` from `AutomationProperties.Name`; confirm with a control that sets both.
- App MCP 1.3.2 (pinned) versus 1.3.4 (read): the description is versioned in the DLL only; a format
  change between them would not be visible here.
- `Serializer.cs:13` registers a custom `ElementIdentifier` converter that was not read; the
  `HierarchyItem` JSON sample above is reconstructed from the record shapes, not captured.
- Whether `HostingService` can hand the selection controller an `IAppInfoProvider` at the point the
  host attaches (`HostingService.cs:63` does it for `ViewModel`; the host itself was not traced).
- `diff_graph.py` keys identity on `(node type, xName)`; consider matching `xName` across node types so
  a mechanical runtime graph needs no `--design` hint. Plugin change, not Hot Design.
- On the Windows TFM `UnoElementRef` is empty (`ElementIdentifierWithRef.cs:16`), so the bridge is
  desktop/WASM/mobile only.
