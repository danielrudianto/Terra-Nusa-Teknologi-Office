const REQUIRED = ["DATABASE_URL", "SECRET_KEY"] as const

export function validateEnv() {
  const missing = REQUIRED.filter(k => !process.env[k])
  if (missing.length) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`)
  }
}
