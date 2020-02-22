const path = require('path');

module.exports = {
  output: {
    path: path.join(__dirname, '/static'),
    filename: 'dist.js'
  },
  module: {
    rules: [
      { test: /\.(ts|tsx)$/, use: 'babel-loader' }
    ]
  },
  resolve: {
    extensions: [
      '.js',
      '.jsx',
      '.web.js',
      '.ts',
      '.tsx'
    ]
  }

};
