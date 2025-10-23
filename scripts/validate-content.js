#!/usr/bin/env node

/**
 * Content Validation Script for RasQberry Two Website
 *
 * Checks for:
 * - Broken internal markdown links
 * - Missing images/assets
 * - Dead external links (optional)
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const CONTENT_DIR = path.join(__dirname, '../content');
const PUBLIC_DIR = path.join(__dirname, '../public');

let errors = [];
let warnings = [];

// Collect all markdown files
function getAllMarkdownFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      getAllMarkdownFiles(filePath, fileList);
    } else if (file.endsWith('.md')) {
      fileList.push(filePath);
    }
  });

  return fileList;
}

// Extract links from markdown content
function extractLinks(content, filePath) {
  const links = {
    internal: [],
    images: [],
    external: []
  };

  // Match markdown links: [text](url)
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;

  while ((match = linkRegex.exec(content)) !== null) {
    let url = match[2];
    // Strip title attribute if present (e.g., 'link.md "Title"' -> 'link.md')
    url = url.split('"')[0].split("'")[0].trim();

    if (url.startsWith('http://') || url.startsWith('https://')) {
      links.external.push({ url, text: match[1], file: filePath });
    } else if (url.match(/\.(png|jpg|jpeg|gif|svg|webp)$/i)) {
      links.images.push({ url, text: match[1], file: filePath });
    } else if (!url.startsWith('#') && !url.startsWith('mailto:')) {
      links.internal.push({ url, text: match[1], file: filePath });
    }
  }

  // Match image tags: ![alt](url)
  const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
  while ((match = imageRegex.exec(content)) !== null) {
    let url = match[2];
    // Strip title attribute if present (e.g., 'image.jpg "Figure 1"' -> 'image.jpg')
    url = url.split('"')[0].split("'")[0].trim();
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      links.images.push({ url, text: match[1], file: filePath });
    }
  }

  return links;
}

// Check if internal link exists
function checkInternalLink(link, sourceFile) {
  const sourceDir = path.dirname(sourceFile);
  let targetPath;

  // Handle absolute paths from content root
  if (link.url.startsWith('/')) {
    // For Next.js routes, check in content directory
    targetPath = path.join(__dirname, '../content', link.url);

    // Also check in public directory
    if (!fs.existsSync(targetPath) && !fs.existsSync(targetPath + '.md')) {
      targetPath = path.join(PUBLIC_DIR, link.url);
    }
  } else {
    targetPath = path.join(sourceDir, link.url);
  }

  // Check if file exists (with or without .md extension)
  if (!fs.existsSync(targetPath)) {
    if (!fs.existsSync(targetPath + '.md')) {
      errors.push({
        type: 'broken-link',
        file: path.relative(process.cwd(), sourceFile),
        link: link.url,
        text: link.text
      });
      return false;
    }
  }

  return true;
}

// Check if image exists
function checkImage(image, sourceFile) {
  const sourceDir = path.dirname(sourceFile);
  let imagePath;

  // Handle absolute paths from public directory
  if (image.url.startsWith('/')) {
    imagePath = path.join(PUBLIC_DIR, image.url);
  } else if (image.url.startsWith('../')) {
    imagePath = path.join(sourceDir, image.url);
  } else {
    imagePath = path.join(sourceDir, image.url);
  }

  if (!fs.existsSync(imagePath)) {
    errors.push({
      type: 'missing-image',
      file: path.relative(process.cwd(), sourceFile),
      image: image.url,
      text: image.text || '(no alt text)'
    });
    return false;
  }

  return true;
}

// Check external link (with timeout)
function checkExternalLink(link) {
  return new Promise((resolve) => {
    const urlObj = new URL(link.url);
    const protocol = urlObj.protocol === 'https:' ? https : http;

    const req = protocol.get(link.url, { timeout: 5000 }, (res) => {
      if (res.statusCode >= 400) {
        warnings.push({
          type: 'dead-external-link',
          file: path.relative(process.cwd(), link.file),
          link: link.url,
          status: res.statusCode
        });
      }
      resolve();
    });

    req.on('error', (err) => {
      warnings.push({
        type: 'external-link-error',
        file: path.relative(process.cwd(), link.file),
        link: link.url,
        error: err.message
      });
      resolve();
    });

    req.on('timeout', () => {
      req.destroy();
      warnings.push({
        type: 'external-link-timeout',
        file: path.relative(process.cwd(), link.file),
        link: link.url
      });
      resolve();
    });
  });
}

// Main validation function
async function validate() {
  console.log('🔍 Validating content...\n');

  const markdownFiles = getAllMarkdownFiles(CONTENT_DIR);
  console.log(`Found ${markdownFiles.length} markdown files\n`);

  const allExternalLinks = [];

  // Check each markdown file
  for (const file of markdownFiles) {
    const content = fs.readFileSync(file, 'utf-8');
    const links = extractLinks(content, file);

    // Check internal links
    links.internal.forEach(link => checkInternalLink(link, file));

    // Check images
    links.images.forEach(image => checkImage(image, file));

    // Collect external links
    allExternalLinks.push(...links.external);
  }

  // Optionally check external links (can be slow)
  if (process.argv.includes('--check-external')) {
    console.log(`\n🌐 Checking ${allExternalLinks.length} external links (this may take a while)...\n`);
    await Promise.all(allExternalLinks.map(checkExternalLink));
  }

  // Report results
  console.log('📊 Validation Results:\n');

  if (errors.length === 0 && warnings.length === 0) {
    console.log('✅ No issues found!\n');
    return 0;
  }

  if (errors.length > 0) {
    console.log(`❌ Found ${errors.length} error(s):\n`);

    errors.forEach(err => {
      if (err.type === 'broken-link') {
        console.log(`  ⛓️  Broken link in ${err.file}`);
        console.log(`     Link: ${err.link}`);
        console.log(`     Text: "${err.text}"\n`);
      } else if (err.type === 'missing-image') {
        console.log(`  🖼️  Missing image in ${err.file}`);
        console.log(`     Image: ${err.image}`);
        console.log(`     Alt text: "${err.text}"\n`);
      }
    });
  }

  if (warnings.length > 0) {
    console.log(`⚠️  Found ${warnings.length} warning(s):\n`);

    warnings.forEach(warn => {
      if (warn.type === 'dead-external-link') {
        console.log(`  🔗 Dead external link in ${warn.file}`);
        console.log(`     Link: ${warn.link}`);
        console.log(`     Status: ${warn.status}\n`);
      } else if (warn.type === 'external-link-error') {
        console.log(`  🔗 External link error in ${warn.file}`);
        console.log(`     Link: ${warn.link}`);
        console.log(`     Error: ${warn.error}\n`);
      } else if (warn.type === 'external-link-timeout') {
        console.log(`  🔗 External link timeout in ${warn.file}`);
        console.log(`     Link: ${warn.link}\n`);
      }
    });
  }

  return errors.length > 0 ? 1 : 0;
}

// Run validation
validate()
  .then(exitCode => {
    console.log('\n' + '='.repeat(60));
    if (exitCode === 0) {
      console.log('✅ Content validation passed!');
    } else {
      console.log('❌ Content validation failed!');
      console.log('\nTip: Run with --check-external to also validate external links');
    }
    console.log('='.repeat(60) + '\n');
    process.exit(exitCode);
  })
  .catch(err => {
    console.error('❌ Validation error:', err);
    process.exit(1);
  });
