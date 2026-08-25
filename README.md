# Senzing Bootcamp Kiro Power

A guided bootcamp for learning [Senzing] entity resolution,
packaged as a Kiro Power.
Install it, then say **"start the bootcamp"** to be guided through
a hands-on, module-by-module tutorial.

## What the bootcamp covers

A guided sequence of hands-on modules takes you from zero
to working entity resolution:

- ***Bootcamp preparation:*** choose your curriculum, level of detail, and programming language
- ***Entity Resolution Concepts:*** a primer on how entity resolution works *(optional)*
- ***Discover the Business Problem:*** describe the problem you are trying to solve
- ***SDK setup:*** install and configure the Senzing SDK
- ***System verification:*** end-to-end checks that Senzing works on your machine *(optional)*
- ***Truth Set visualization:*** an interactive web app of the resolved Truth Set data *(optional)*
- ***Data collection:*** identify and collect your data sources
- ***Data Quality, Mapping, and Transformation:*** make your data "Senzing-ready"
- ***Data processing:*** ingest your Senzing-ready data
- ***Query, Visualize and Discover:*** see what Senzing can do for you
- ***Bootcamp graduation:*** wrap up your bootcamp with a bow

You finish with working Senzing code and data in your project, a professional
recap PDF you can keep and share, and a production starter. See
[What you finish with](#what-you-finish-with) for details.

## Requirements

- Network access to the [Senzing MCP server].
  The bootcamp cannot proceed without it.
  It generates SDK code,
  looks up Senzing facts,
  and provides working examples.
- Minimum of 2000 [Kiro credits].
- *Recommended, but not mandatory:*
  A business problem requiring Entity Resolution
  and 5,000 to 20,000 records that illustrate the problem.

## Install and start

1. [Install Kiro]
1. From a terminal window, start Kiro in a new, empty directory.
   Example:

    ```console
    mkdir senzing-bootcamp
    cd senzing-bootcamp
    kiro .
    ```

    - In macOS, start "Kiro" and open a new project on an empty directory.

1. Install the Senzing Bootcamp Power.
    1. In Kiro's left-hand icon bar, click on the **Powers** icon.
    1. In the **Powers** panel, under **Installed**, click on "Add Custom Power".
    1. Select "Import power from GitHub"
    1. Enter the following GitHub repository URL:

        ```text
        https://github.com/Senzing/senzing-bootcamp-kiro-power/tree/main/senzing-bootcamp
        ```

1. In Kiro's agentic chat, enter the following to begin the bootcamp:

    ```console
    Start the bootcamp
    ```

Kiro's agentic chat will guide you through the Bootcamp.

## What you finish with

The bootcamp is a guided, module-by-module tutorial.
You end with working Senzing code and data in your project (`src/`, `data/`, `database/`),
a professional recap PDF you can keep and share (e.g. [bootcamp_recap.pdf], but yours will differ),
and a `production/` starter project.

[bootcamp_recap.pdf]: https://raw.githubusercontent.com/docktermj/senzing-bootcamp-claude-plugin-development/refs/heads/main/plugins/senzing-bootcamp/docs/examples/bootcamp_recap.example.pdf
[Install Kiro]: https://kiro.dev/
[Kiro credits]: https://kiro.dev/pricing/
[Senzing MCP server]: https://mcp.senzing.com/mcp
[Senzing]: https://senzing.com
