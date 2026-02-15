const express = require('express');
const path = require('path');
const app = express();
const port = 3000;

// Serve static files from the frontend directory
app.use(express.static(path.join(__dirname)));

// Handle API requests by proxying to the backend
const { createProxyMiddleware } = require('http-proxy-middleware');

app.use('/api', createProxyMiddleware({
  target: 'http://backend:8000', // Backend service name in Docker Compose
  changeOrigin: true,
  pathRewrite: {
    '^/api': '', // Remove /api prefix when forwarding to backend
  },
}));

// Also proxy other API endpoints that might be needed
app.use('/login', createProxyMiddleware({
  target: 'http://backend:8000',
  changeOrigin: true,
}));

// Serve the index.html file for all other routes that don't match static files
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Catch-all route for other pages that should be handled by frontend routing
app.get('*', (req, res) => {
  // Check if the requested path corresponds to a static file
  const requestedFilePath = path.join(__dirname, req.path.substring(1)); // remove leading slash
  
  // For API-like routes, we should return a 404 or handle differently
  if (req.path.startsWith('/api/') || req.path.includes('.')) {
    res.status(404).send('Not Found');
  } else {
    // For frontend routes, serve the main index.html file
    res.sendFile(path.join(__dirname, 'index.html'));
  }
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server running at http://localhost:${port}`);
});