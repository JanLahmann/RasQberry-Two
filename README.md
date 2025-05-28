# RasQberry Two GitHub Pages

[![Deploy Next.js site to Pages](https://github.com/JanLahmann/RasQberry-Two/actions/workflows/nextjs.yml/badge.svg)](https://github.com/JanLahmann/RasQberry-Two/actions/workflows/nextjs.yml)

Welcome to the **RasQberry Two** GitHub Pages repository! This project documents the functional model of **IBM Quantum System TWO**, featuring enhancements such as:

- 64-bit platform support
- Integration with **Raspberry Pi 5**
- Support for **Qiskit 1.x**
- Expanded quantum computing demos
- Integration with `raspi-config`

If you're looking for the functional model of IBM Quantum System ONE, visit [rasqberry.one](https://rasqberry.one).

To get started with the project, have a look at the description and documentation at [rasqberry.org](https://rasqberry.org) or dive into the source code in this repo.

---

## 🚀 Project Overview

This repository powers the RasQberry Two documentation website, built using **Next.js** and deployed via **GitHub Actions**.

### Features:

- **Dynamic Content**: Markdown-based pages rendered as part of the website.
- **Customizable Frontmatter**: Define page metadata like titles, leadspaces, and table of contents settings.
- **Modern Tooling**: Leverages Next.js for static site generation and optimized builds.

---

## 🛠 How to Start Developing

### Prerequisites

- **Node.js**: Version 20 is required. [Install Node.js](https://nodejs.org/en/download/package-manager).

### Setup Instructions

1. **Install Dependencies**:
   ```bash
   npm install
   ```
2. **Run in Development Mode:**:
   ```bash
   npm run dev
   ```
3. **Build for Production:**:
   ```bash
   npm run build
   ```
4. **Serve Production Build:**:
   ```bash
   npx serve@latest out
   ```
     
## 📚 How to Add Content

The website builds its pages dynamically from the [content](https://github.com/JanLahmann/RasQberry-Two/tree/gh-pages/content) folder. Each Markdown file in this folder corresponds to a page on the site, maintaining the folder's route hierarchy.

### Markdown File Structure

Each Markdown file consists of:

1. **Frontmatter (Optional):** YAML configuration enclosed in `---`. This section specifies metadata and page attributes.
2. **Content:** The main body written in standard Markdown syntax.

### Frontmatter Attributes

Here’s a breakdown of available attributes for configuration:

```
leadspace:
  title: string             # Title of the page
  copy: string              # Subtitle or description
  size: tall | short | super # Height of the leadspace section
  cta:                      # Optional Call-to-Action configuration
    primary:
      label: string         # Button text
      url: string           # Button URL
      icon: logo-github | arrow-right # Icon for the button
  bg:                       # Optional background settings
    image:
      src: string           # Image URL
      alt: string           # Alt text for the image
tableOfContent:
  disabled: boolean         # Disable TOC for this page (true/false) default false
  minLevel: number          # Minimum header level to include in TOC
  maxLevel: number          # Maximum header level to include in TOC
```

### Additional Markdown Features

You can enhance your Markdown files using custom directives:

#### Embedding YouTube Videos

Embed a YouTube video by adding the following directive to your Markdown file:

```
::youtube[Description of the video]{#video-id}
```

Example:

```
::youtube[Video of a cat in a box]{#2yJgwwDcgV8}
```

## 🤝 Contributing

### Bug Reports and Feature Requests

We welcome contributions! If you encounter a bug or have ideas for new features, please open an issue here.

### Submitting Changes

1. Fork the repository and create your feature branch.
2. Commit your changes with a descriptive message.
3. Push the branch to your fork and create a Pull Request.

## 🧩 Resources

- [Next.js Documentation](https://nextjs.org)
- [Markdown Guide](https://www.markdownguide.org)
- [GitHub Actions Documentation](https://docs.github.com/es/actions)