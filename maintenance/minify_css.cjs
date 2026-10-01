const CleanCSS = require('clean-css');

if (process.argv.length !== 3) {
  console.error('Use: node maintenance/minify_css.cjs <source.css>');
  process.exit(1);
}

const result = new CleanCSS({ level: 2, rebase: false }).minify([process.argv[2]]);
const messages = [...result.errors, ...result.warnings];
if (messages.length) {
  console.error(messages.join('\n'));
  process.exit(1);
}
process.stdout.write(result.styles);
