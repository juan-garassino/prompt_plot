; 5-pointed star drawing example
; Created for PromptPlot demo
G28                    ; Home
G90                    ; Absolute positioning
G0 X25 Y5              ; Move to start (bottom point)
M3 S1000               ; Pen down
G1 X30 Y20 F1000       ; To right inner
G1 X45 Y20 F1000       ; To right point
G1 X33 Y30 F1000       ; To right inner upper
G1 X38 Y45 F1000       ; To top right point
G1 X25 Y35 F1000       ; To top inner
G1 X12 Y45 F1000       ; To top left point
G1 X17 Y30 F1000       ; To left inner upper
G1 X5 Y20 F1000        ; To left point
G1 X20 Y20 F1000       ; To left inner
G1 X25 Y5 F1000        ; Back to start (close star)
M5                     ; Pen up
G0 X0 Y0               ; Return to origin
G28                    ; Home
