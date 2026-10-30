const { marked } = require('marked');
console.log(marked.parse('<iframe src="/plugin/media"></iframe>'));
