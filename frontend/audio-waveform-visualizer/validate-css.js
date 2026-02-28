const fs = require('fs');
const path = require('path');const postcss = require('postcss');
const cssnano = require('cssnano');

const srcDir = path.join(__dirname, 'src');

function findCssFiles(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  
  list.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat && stat.isDirectory()) {
      results = results.concat(findCssFiles(filePath));
    } else if (file.endsWith('.css')) {
      results.push(filePath);
    }
  });
  
  return results;
}

async function validateCss(filePath) {
  try {
    const css = fs.readFileSync(filePath, 'utf8');
    await postcss([cssnano({ preset: 'default' })]).process(css, { from: filePath });
    console.log(`✓ ${filePath}`);
    return null;
  } catch (error) {
    console.error(`✗ ${filePath}:`);
    console.error(`  ${error.message}`);
    if (error.line) {
      console.error(`  Line: ${error.line}, Column: ${error.column}`);
    }
    return { filePath, error };
  }
}

async function main() {
  console.log('Finding CSS files...');
  const cssFiles = findCssFiles(srcDir);
  console.log(`Found ${cssFiles.length} CSS files\n`);
  
  const errors = [];
  
  for (const file of cssFiles) {
    const error = await validateCss(file);
    if (error) errors.push(error);
  }
  
  console.log('\n=== Summary ===');
  if (errors.length === 0) {
    console.log('All CSS files are valid!');
  } else {
    console.log(`Found ${errors.length} error(s):`);
    errors.forEach(({ filePath, error }) => {
      console.log(`\n${filePath}:`);
      console.log(`  ${error.message}`);
    });
  }
}

main();
