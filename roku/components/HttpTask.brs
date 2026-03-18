' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

sub init()
    m.top.functionName = "doFetch"
end sub

sub doFetch()
    req = m.top.request
    if req = invalid or req.url = invalid or req.url = "" then return

    http = CreateObject("roUrlTransfer")
    http.SetUrl(req.url)
    http.SetCertificatesFile("common:/certs/ca-bundle.crt")
    http.InitClientCertificates()
    http.EnableEncodings(true)

    method = "GET"
    if req.method <> invalid then method = req.method

    if method = "POST"
        http.addHeader("Content-Type", "application/json")
        body = ""
        if req.body <> invalid then body = req.body
        result = http.PostFromString(body)
        ' PostFromString returns response code, need AsyncPostFromString for body
        ' Use GetToString pattern with roUrlEvent instead
        m.top.response = str(result)
    else
        result = http.GetToString()
        if result <> invalid
            m.top.response = result
        else
            m.top.response = ""
        end if
    end if
end sub
