; GCode for four separate lines
G21 ; Set units to millimeters
G90 ; Absolute positioning
M3 S1000 ; Enable tool

; First line
G0 Z5 ; Lift pen
G0 X20 Y20 ; Move to start of first line
G0 Z0 ; Lower pen
G1 X80 Y20 ; Draw first line
G0 Z5 ; Lift pen

; Second line
G0 X20 Y40 ; Move to start of second line
G0 Z0 ; Lower pen
G1 X80 Y40 ; Draw second line
G0 Z5 ; Lift pen

; Third line
G0 X20 Y60 ; Move to start of third line
G0 Z0 ; Lower pen
G1 X80 Y60 ; Draw third line
G0 Z5 ; Lift pen

; Fourth line
G0 X20 Y80 ; Move to start of fourth line
G0 Z0 ; Lower pen
G1 X80 Y80 ; Draw fourth line
G0 Z5 ; Lift pen

; Return to origin
G0 X0 Y0 ; Return to home
M5 ; Disable tool
M2 ; End program