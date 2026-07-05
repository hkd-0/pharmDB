export async function onRequest(context) {
    // 1. Grab the hidden Render URL from Cloudflare's environment
    const backendUrl = context.env.BACKEND_URL;
    
    // 2. Grab the original request coming from your index.html
    const originalRequest = context.request;

    // 3. Forward the request to Render, keeping the x-api-key header intact
    const backendResponse = await fetch(backendUrl, {
        method: originalRequest.method,
        headers: originalRequest.headers,
        body: originalRequest.body
    });

    // 4. Return the data to the frontend
    return backendResponse;
}