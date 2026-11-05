# TypeScript Studio

Start the engine from the repository root with `.venv/bin/python magic.py serve`. In this directory run `npm ci` and `npm run dev`, then open the displayed local URL and enter an existing project folder. The timeline is read-only: selecting a version does not roll it back. Models are saved with a version when its gates run; older versions without saved models can be rebuilt in an isolated temporary copy using the Rebuild model button. The project files and version timeline are not changed. If the checks no longer agree with the saved verdict, the rebuilt model is not shown.

Run `npm test` for type checking and Playwright against a real local engine and temporary project. It requires Google Chrome, the repository's Python environment and free ports 5173 and 8766. The test runs the fixture gates twice and removes its temporary project afterward.
