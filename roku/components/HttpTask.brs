' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.top.functionName = "doRequest"
end sub

sub doRequest()
    req = m.top.request
    if req = invalid or req.url = invalid or req.url = ""
        m.top.error = "Invalid request"
        return
    end if

    port = CreateObject("roMessagePort")
    http = CreateObject("roUrlTransfer")
    http.SetMessagePort(port)
    http.SetUrl(req.url)
    http.SetCertificatesFile("common:/certs/ca-bundle.crt")
    http.InitClientCertificates()
    http.EnableEncodings(true)

    ' Add Authorization header if credentials are provided
    if req.auth <> invalid and req.auth.username <> invalid and req.auth.username <> "" and req.auth.password <> invalid
        authStr = req.auth.username + ":" + req.auth.password
        ba = CreateObject("roByteArray")
        ba.FromAsciiString(authStr)
        http.AddHeader("Authorization", "Basic " + ba.ToBase64String())
    end if

    method = "GET"
    if req.method <> invalid then method = req.method

    ' Execute request asynchronously
    if method = "POST"
        http.AddHeader("Content-Type", "application/json")
        body = ""
        if req.body <> invalid then body = req.body
        if not http.AsyncPostFromString(body)
            m.top.error = "Failed to start POST request"
            return
        end if
    else ' Default to GET
        if not http.AsyncGetToString()
            m.top.error = "Failed to start GET request"
            return
        end if
    end if

    ' Wait for the response event
    while true
        msg = wait(10000, port) ' 10 second timeout
        if type(msg) = "roUrlEvent"
            m.top.responseCode = msg.GetResponseCode()
            if m.top.responseCode = 200
                m.top.response = msg.GetString()
            else
                m.top.error = "HTTP " + m.top.responseCode.toStr()
            end if
            return
        else if msg = invalid
            m.top.error = "Request timed out"
            return
        end if
    end while
end sub
