# RasQberry Two Github pages

This is the github pages project for the RasQberry Two documentation page.

Is build using NextJS and deployed using Github Actions.

## How add content

The project is prepared to build the pages from the [`content`](https://github.com/paaragon/rasqberry-two-dev/tree/main/content) folder. It will create the same route hierarchy that is contained in the folder.

The `content` folder should contain Markdown files. Each file will be rendered and served as a page in the website.

## Markdown page structure

Each markdown page have two sections:

- Frontmatter (optional): it is defined at the top of the file and delimited with `---` at the beginning and at the end of the section.
- Content: the markdown content that will be rendered as the page content.

### Frontmatter structure

We can define the following atributes in the frontmatter of each page:

leadspace:
  title: RasQberry Two
  copy: "The RasQberry project: Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer"
  size: tall
  cta:
    primary:
      label: View On GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
  bg:
    image:
      src: https://picsum.photos/id/1076/1056/480
      alt: lead space background image

### Markdown syntax available

Apart from the standard Markdown syntax, there are some directives availables:

#### Youtube videos

```
::youtube[description of the video]{#video-id}
```

Example

```
::youtube[Video of a cat in a box]{#2yJgwwDcgV8}
```