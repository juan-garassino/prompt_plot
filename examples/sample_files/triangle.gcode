; Triangle drawing example
; Created for PromptPlot demo
G28                    ; Home
G90                    ; Absolute positioning
G0 X10 Y10             ; Move to start position
M3 S1000               ; Pen down
G1 X30 Y10 F1000       ; Bottom edge
G1 X20 Y25 F1000       ; Right edge
G1 X10 Y10 F1000       ; Left edge (close triangle)
M5                     ; Pen up
G0 X0 Y0               ; Return to origin
G28                    ; Home
