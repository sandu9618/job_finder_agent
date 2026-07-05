{
  ...original fields...,
  "description": str,           # sanitized
  "redacted_categories": [str], # e.g. ["email", "phone"]
  "security_flag": bool,        # true if injection suspected
  "security_reason": str | null
}
