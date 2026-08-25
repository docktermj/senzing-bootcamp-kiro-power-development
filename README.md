# Senzing Bootcamp Kiro Power

This repository contains the Senzing Bootcamp Kiro Power and its development documentation.

The goal of this bootcamp is that you can say to yourself,
"I can do this!"

## Prerequisites

1. [Install Kiro](docs/install-kiro.md)
    - Make sure you are using Kiro 1.0.0 or greater. (`Help` > `About`)

## Start Kiro in a Senzing Bootcamp directory

1. From a terminal window, start Kiro in a new, empty directory.
   Example:

    ```console
    mkdir senzing-bootcamp
    cd senzing-bootcamp
    kiro .
    ```

1. In macOS, start "Kiro" and open a new project on an empty directory.

## Configure Kiro

1. In Kiro's agentic chat, switch from "Auto" to "Claude Opus 4.8 high".

## Install the Senzing Bootcamp Power

1. In Kiro's left-hand icon bar, click on the **Powers** icon.
1. In the **Powers** panel, under **Installed**, click on "Add Custom Power".
1. Select "Import power from GitHub"
1. Enter the following GitHub repository URL:

   ```text
   https://github.com/Senzing/senzing-bootcamp-kiro-power/tree/main/senzing-bootcamp
   ```

## Follow the Senzing Bootcamp

In Kiro's agentic chat, enter the following to begin the bootcamp:

```console
Start the bootcamp
```

Kiro's agentic chat will guide you through the Bootcamp.

## Tips

1. **Caveat:** At times, the Bootcamp may seem boring.
   If it wasn't boring,
   *you* would have to do the work.
   Your job is to steer the AI to create what you want.
   Let the AI do the work.
1. During "Administrative setup", simply hitting the "Allow" button is all that's needed.
1. Questions posed to the Bootcamper are usually prefaced with "👉"

## Peccadillos

- The "Roomba effect".
  The AI-driven bootcamp may head directly into an error, recover, and head in a new direction.
- Most likely your main Agentic Chat will be in a tabbed panel named "Start the Bootcamp".
  Occasionally, additional "New Session" tabbed panels will pop up.
  They are for sub-agents.
  They do a small task and exit.
  When you see something like:

  > Est. Credits Used: 0.42 Elapsed time: 9s

  You'll know the sub-agent has completed and the tabbed panel may be closed.
- Numerous "Ask Kiro Hook" boxes will appear.
  These boxes and the text following are mostly noise.
  Unfortunately, there's no way to turn off those boxes.
- If Kiro seems to be stuck, ask

  ```console
  What are you working on?
  ```

## Helpful prompts

Helpful prompts that can may entered any time:

```console
Where am I in the bootcamp?
```

```console
What's next?
```

```console
Why am I doing this?
```

```console
What was done?
```

```console
Why did you do that?
```

```console
What does ____ mean?
```

```console
Where did you put ____?
```

```console
How does what was built in module number ____ help me?
```

## Reporting Bootcamp improvements

To report a bug or improvement, start your prompt with `Bootcamp Feedback:`.
Example:

```console
Bootcamp Feedback: You asked me to recommend a restaurant. That shouldn't be asked in the bootcamp.
```

## Clean up the Bootcamp

1. Move any files you'd like to keep out of the project directory.
   Examples:  Backup file(s), prompt history file, source code (`src/`).

1. **Delete the Senzing Bootcamp project directory.**

   Since all of the artifacts created by the bootcamp are in the bootcamp directory,
   simply delete the bootcamp directory.
   Examples:

   - **Linux / macOS:**

     ```console
     rm -rf senzing-bootcamp
     ```

   - **Windows (Command Prompt):**

     ```console
     rmdir /s /q senzing-bootcamp
     ```

   - **Windows (PowerShell):**

     ```powershell
     Remove-Item -Recurse -Force senzing-bootcamp
     ```

1. **(Optional) Remove the Senzing Bootcamp Power:**
   1. In Kiro's left-hand icon bar, click on the **Powers** icon.
   1. In the **Powers** panel, under **Installed**, find "Senzing Bootcamp".
   1. In the **Power: Senzing Bootcamp** panel, click the **Uninstall** button.
