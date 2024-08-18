[![Deploy Next.js site to Pages](https://github.com/JanLahmann/RasQberry-Two/actions/workflows/nextjs.yml/badge.svg)](https://github.com/JanLahmann/RasQberry-Two/actions/workflows/nextjs.yml)

# RasQberry Two Github pages

This is the GitHub Pages project for the RasQberry Two documentation page.

It is built using NextJS and deployed using GitHub Actions.

## How to start developing

### Prerequisites

- NodeJS 20 ([how to install](https://nodejs.org/en/download/package-manager))

### Install dependencies

```
npm install
```

### Run the website in development mode

```
npm run dev
```


### Build and run in production mode

```
npm run build
npx serve@latest out
```

## How add content

The project is set up to build the pages from the [`content`](https://github.com/paaragon/rasqberry-two-dev/tree/main/content) folder. It will create the same route hierarchy contained in the folder.

The `content` folder should contain Markdown files. Each file will be rendered and served as a page on the website.

## Markdown page structure

Each markdown page have two sections:

- Frontmatter (optional): it is defined at the top of the file and delimited with `---` at the beginning and end of the section.
- Content: The Markdown content that will be rendered as the page content.

### Frontmatter structure

We can define the following attributes in the frontmatter of each page:

```
leadspace:
  title: string
  copy: string
  size: tall | short | super
  cta: (optional)
    primary:
      label: text for the CTA button
      url: url for the CTA button
      icon: logo-github | arrow-right
  bg: (optional)
    image:
      src: url for the image
      alt: alternative text for the image
```

### Markdown syntax available

Apart from the standard Markdown syntax, there are some directives available:

#### Youtube videos

```
::youtube[description of the video]{#video-id}
```

Example

```
::youtube[Video of a cat in a box]{#2yJgwwDcgV8}
```
