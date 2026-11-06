# Watermelon UI adaptations

The source was retrieved through Watermelon UI's public MCP server:
https://mcp.watermelon.sh/mcp

- ButtonGroup 3/12: https://ui.watermelon.sh/components/button-group
  Registries: https://registry.watermelon.sh/r/button-group-3.json and
  https://registry.watermelon.sh/r/button-group-12.json
- Popover 9: https://ui.watermelon.sh/components/popover
  Registry: https://registry.watermelon.sh/r/popover-9.json
- Command Search: https://ui.watermelon.sh/animated-components/command-search
  Registry: https://registry.watermelon.sh/r/command-search.json
- Tooltip 8: https://ui.watermelon.sh/components/tooltip
  Registry: https://registry.watermelon.sh/r/tooltip-8.json

Adapted to this existing React 19 / Vite / plain CSS application. The command
search keeps the catalog pattern of filtering, sections, active-index navigation,
keyboard dismissal and actual item actions. Studio supplies only supported local
commands. Native dialog provides focus containment and restoration. Watermelon's
sample/demo actions and marketing copy are omitted. Existing custom icons and
CSS tokens replace the example's icon libraries and Tailwind classes. No animation
package is required; reduced-motion behavior remains local.

The tooltip adopts the source's compact explanatory/keyboard-hint pattern, with
portal positioning so the toolbar cannot clip it, and focus as well as pointer
access. Public catalog access is design-time only; the application never requires
Watermelon's service to run.

MIT License

Copyright (c) 2026 Watermelon Platform Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

ButtonGroup 3/12 contribute compact grouped icon actions and icon/label segments;
Popover 9 contributes grouped settings, live range readout and a reset action.
The adaptation uses native HTML popover, checkbox and range controls with real
Three.js appearance state, rather than the catalog's sample filters or budget.
All CAD icons are original vector drawings, not Watermelon/Lucide icon assets.
