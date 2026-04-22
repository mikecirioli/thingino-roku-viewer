' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

' ============================================================================
' Utils.brs — shared helpers for URL construction and remote-access auth.
' ============================================================================
'
' Registry model (roRegistrySection("settings")):
'   serverUrl  — base URL, e.g. "http://192.168.1.245:8099" (LAN) or
'                "https://cirioli.duckdns.org/photoframe" (remote)
'   serverAuth — optional shared secret. If set, appended as ?auth=<secret>
'                (or &auth=<secret> when path already contains '?') to every
'                URL built by buildUrl().
'
' Callers should prefer buildUrl(baseUrl, path) over raw string concatenation.
' If serverAuth is unset/empty, buildUrl() behaves exactly like the old
' `baseUrl + path` concatenation — preserving LAN fallback.

' -----------------------------------------------------------------------------
' buildUrl(baseUrl, path)
'   Combines baseUrl + path and appends auth query param if secret is present.
'
'   Args:
'     baseUrl - The server base URL (typically m.SERVER_URL read from registry).
'     path    - Path portion, starting with "/". May already contain "?...".
'
'   Returns:
'     String URL with auth appended when serverAuth registry key is set.
' -----------------------------------------------------------------------------
function buildUrl(baseUrl as string, path as string) as string
    url = baseUrl + path
    secret = getServerAuth()
    if secret <> ""
        sep = "?"
        if Instr(1, url, "?") > 0 then sep = "&"
        url = url + sep + "auth=" + urlEncode(secret)
    end if
    return url
end function

' -----------------------------------------------------------------------------
' getServerAuth()
'   Reads serverAuth from roRegistrySection("settings"). Returns "" if unset.
' -----------------------------------------------------------------------------
function getServerAuth() as string
    sec = CreateObject("roRegistrySection", "settings")
    secret = sec.Read("serverAuth")
    if secret = invalid then return ""
    return secret
end function

' -----------------------------------------------------------------------------
' urlEncode(s)
'   Percent-encodes a string for safe use in URL query parameters.
'   Uses roUrlTransfer.Escape() when available; falls back to manual encoding.
' -----------------------------------------------------------------------------
function urlEncode(s as string) as string
    if s = invalid or s = "" then return ""
    xfer = CreateObject("roUrlTransfer")
    if xfer <> invalid and GetInterface(xfer, "ifUrlTransfer") <> invalid
        return xfer.Escape(s)
    end if
    ' Fallback — manual encoding of common unsafe chars.
    result = ""
    for i = 1 to Len(s)
        c = Mid(s, i, 1)
        code = Asc(c)
        isAlnum = (code >= 48 and code <= 57) or (code >= 65 and code <= 90) or (code >= 97 and code <= 122)
        isSafe  = (c = "-" or c = "_" or c = "." or c = "~")
        if isAlnum or isSafe
            result = result + c
        else
            hex = StrI(code, 16)
            if Len(hex) = 1 then hex = "0" + hex
            result = result + "%" + UCase(hex)
        end if
    next
    return result
end function

' -----------------------------------------------------------------------------
' maskSecret(s)
'   Masks a secret for display in the Settings UI. Shows last 4 chars.
' -----------------------------------------------------------------------------
function maskSecret(s as string) as string
    if s = invalid or s = "" then return ""
    n = Len(s)
    if n <= 4 then return "****"
    tail = Right(s, 4)
    return "••••••••" + tail
end function
