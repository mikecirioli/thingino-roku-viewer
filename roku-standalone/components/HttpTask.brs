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

    authType = m.top.authType
    session = m.top.session

    ' Thingino login if needed
    if authType = "thingino" and (session = invalid or session = "")
        if req.auth <> invalid and req.auth.username <> invalid and req.auth.password <> invalid
            host = extractHost(req.url)
            session = loginThingino(host, req.auth.username, req.auth.password)
            if session <> ""
                m.top.session = session
            else
                m.top.error = "Thingino login failed"
                return
            end if
        else
            m.top.error = "Missing credentials for Thingino auth"
            return
        end if
    end if

    port = CreateObject("roMessagePort")
    http = CreateObject("roUrlTransfer")
    http.SetMessagePort(port)
    http.SetUrl(req.url)
    http.SetCertificatesFile("common:/certs/ca-bundle.crt")
    http.InitClientCertificates()
    http.EnableEncodings(true)

    ' Add Authorization or Cookie header
    if authType = "basic" and req.auth <> invalid and req.auth.username <> invalid and req.auth.password <> invalid
        authStr = req.auth.username + ":" + req.auth.password
        ba = CreateObject("roByteArray")
        ba.FromAsciiString(authStr)
        http.AddHeader("Authorization", "Basic " + ba.ToBase64String())
    else if authType = "thingino" and session <> ""
        http.AddHeader("Cookie", "thingino_session=" + session)
    end if

    method = "GET"
    if req.method <> invalid then method = req.method

    ' Execute request asynchronously
    if req.toFile <> invalid and req.toFile <> ""
        if not http.AsyncGetToFile(req.toFile)
            m.top.error = "Failed to start GET to file"
            return
        end if
    else if method = "POST"
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

function loginThingino(host as string, user as string, pass as string) as string
    if host = "" then return ""
    url = "http://" + host + "/x/login.cgi"
    body = FormatJSON({ username: user, password: pass })
    
    port = CreateObject("roMessagePort")
    http = CreateObject("roUrlTransfer")
    http.SetMessagePort(port)
    http.SetUrl(url)
    http.AddHeader("Content-Type", "application/json")
    
    if http.AsyncPostFromString(body)
        msg = wait(5000, port)
        if type(msg) = "roUrlEvent" and msg.GetResponseCode() = 200
            headers = msg.GetResponseHeadersArray()
            for each header in headers
                for each key in header
                    if LCase(key) = "set-cookie"
                        cookie = header[key]
                        if cookie.instr("thingino_session=") >= 0
                            parts = cookie.split(";")
                            for each part in parts
                                if part.trim().instr("thingino_session=") = 0
                                    return part.trim().split("=")[1]
                                end if
                            end for
                        end if
                    end if
                end for
            end for
        end if
    end if
    return ""
end function

function extractHost(url as string) as string
    if Left(url, 7) = "http://"
        host = url.split("/")[2]
        return host
    else if Left(url, 8) = "https://"
        host = url.split("/")[2]
        return host
    end if
    return ""
end function
