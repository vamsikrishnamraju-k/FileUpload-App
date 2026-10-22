# CloudDrop React Frontend

This frontend is now built with React + Vite and served by a small Node.js/Express server.

## Upload rules

- PDF and ZIP only
- Maximum file size: 200 MB
- React rejects invalid files before sending the request.
- The Flask backend validates again before the S3 `PutObject` call.

## Run locally

```bash
npm install
npm run dev
```

For the production container:

```bash
npm run build
npm start
```

Set `BACKEND_URL` to the Flask backend URL when running the Node server.
