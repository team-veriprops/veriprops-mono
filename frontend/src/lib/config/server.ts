if (typeof window !== "undefined") {
  throw new Error("❌ serverConfig imported on the client");
}

export const serverConfig = {
  backendApi: process.env.API_BASE_URL!,
  secretKey: process.env.BACKEND_SECRET_KEY!,
};
