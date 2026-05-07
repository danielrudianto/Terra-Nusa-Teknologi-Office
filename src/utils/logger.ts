const GREEN = "\x1b[92m"
const YELLOW = "\x1b[93m"
const RED = "\x1b[91m"
const RESET = "\x1b[0m"

export function logInfo(message: string) {
  console.log(`${GREEN}INFO${RESET}:     ${message}`)
}

export function logWarning(message: string) {
  console.log(`${YELLOW}WARNING${RESET}:  ${message}`)
}

export function logError(message: string) {
  console.error(`${RED}ERROR${RESET}:    ${message}`)
}
