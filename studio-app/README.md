# TypeScript Studio

Start the engine from the repository root with `.venv/bin/python magic.py serve`. In this directory run `npm ci` and `npm run dev`, then open the displayed local URL and enter an existing project folder. The timeline is read-only: selecting a version does not roll it back. Models are saved with a version when its gates run; older runs from before this feature have no saved model and must be run again to capture one.

Run `npm test` for type checking and Playwright against a real local engine and temporary project. It requires Google Chrome, the repository's Python environment and free ports 5173 and 8766. The test runs the fixture gates twice and removes its temporary project afterward.
