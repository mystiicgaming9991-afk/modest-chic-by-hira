export function isUnauthorizedStaffError(cause: unknown): boolean {
  return cause instanceof Error && "status" in cause && cause.status === 401;
}
