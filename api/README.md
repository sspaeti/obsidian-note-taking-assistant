# FastAPI Embed API

This is the deployment for FastAPI endpoint for BAAI/bge-m3 serving for Vercel deployed app.

As the model is quite big, and Hugging Face interferance API is too slow, we deploying a simple API to railway that we can use in our deployment.

## Deployment steps on Railway

```sh
cd second-brain-rag/api
railway login
railway init    # creates new project
railway up      # deploys
```

Then add `EMBED_API_URL=https://your-railway-url/embed` to Vercel.


2. deployment vercel app again with `make web-redeploy-prod`
