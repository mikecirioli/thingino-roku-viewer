' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

sub init()
    m.nameLabel = m.top.findNode("nameLabel")
    m.typeLabel = m.top.findNode("typeLabel")
    m.bg = m.top.findNode("bg")
end sub

sub onContentChanged()
    content = m.top.itemContent
    if content = invalid then return

    m.nameLabel.text = content.title
    desc = content.description
    if desc <> invalid and desc <> ""
        m.typeLabel.text = desc
    else
        m.typeLabel.text = ""
    end if
end sub

sub onFocusChanged()
    if m.top.focusPercent > 0.5
        m.bg.color = "#3366FF44"
    else
        m.bg.color = "#FFFFFF10"
    end if
end sub
