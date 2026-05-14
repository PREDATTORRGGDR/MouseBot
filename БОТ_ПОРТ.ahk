#SingleInstance Force

F6::
radius := 100      ; радиус круга
steps := 72        ; сколько точек в круге
delay := 10        ; задержка между движениями

Loop, %steps%
{
    angle := A_Index * 6.283185 / steps

    x := Round(Cos(angle) * radius)
    y := Round(Sin(angle) * radius)

    MouseMove, %x%, %y%, 0, R
    Sleep, %delay%

    MouseMove, % -x, % -y, 0, R
}
return

End::ExitApp
