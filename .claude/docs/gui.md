# GUI (Graphical User Interface)

The GUI is the primary mechanism by which the user manages their Blender project.

## Core Features

- Resizeable panel. Users can change the size and position of the GUI
- Clear, concise calls to action that maximize clarity for the user
- Current branch is clearly visible both at the top of the addon panel (if not initialized, display "Not yet initialized") and in the bottom toolbar (next to the Scene Collection stats like vert/faces/tris count)
- Visual timeline of the git history of the project.
  - Moveable and resizeable panel that renders to the left of the addon's panel and should occupy the full height of the screen and a minimum width of 320px.
  - The content window of this panel should be scrollable in the event that the project history is extensive
  - The primary branch should always have the same color which is user-defineable in the addon settings. We'll default to rgb(0, 208, 153)

## State Management

Due to how Git LFS works, we'll need to reload the blender file after every checkout (branch or commit) to ensure that the user is seeing the correct binary.

### Scenario 1: New, unsaved project, no git repository initialized

- Initial State:
  - GUI only displays the "initialize" actions.
  - When clicked, this initialize button should create a directory in the user-defined blender-projects directory
  - If successful, the GUI should then display:
    - A "Create Branch" button
      - clicking this button shows the user a text input where they enter the branch name. The text input should validate whether the branch name is valid. If possible, sanitize the input by replacing space characters with "", for example.
    - A "Commit" button
      - clicking this displays a textarea with a default commit message. User can change.
      - Cancel and Commit buttons either create the commit or cancel changes
      - Before creating the commit, we need to ensure the file is saved for best UX.
    - A dropdown menu (default value being current branch) which lists all branches.
      - When a branch is selected, we first create a commit on the current branch if there are uncommitted changes.
      - The branch is checked out.

## Design Principles

- related operations should be co-located.
- only display the minimum amount of information necessary to illustrate the state of the file and the outcome of each action available to the user. We should never display an action that cannot be performed.
