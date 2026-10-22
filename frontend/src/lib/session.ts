/**
 * ID token of the signed-in emulator user, or null. Firebase is imported on demand so the SDK stays out of the main bundle,
 * and any failure (emulator down, no user, SDK error) means "not signed in" rather than a crash.
 */
export async function getIdToken(): Promise<string | null> {
  try {
    const { auth } = await import('./firebase')
    await auth.authStateReady()
    return auth.currentUser ? await auth.currentUser.getIdToken() : null
  } catch {
    return null
  }
}
