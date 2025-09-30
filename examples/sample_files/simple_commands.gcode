; PromptPlot Sample G-code File
; Simple square drawing for testing
; Units: millimeters
; Created: 2024

; Initialize
G21 ; Set units to millimeters
G90 ; Absolute positioning
G28 ; Home all axes
M3 S0 ; Pen up

; Move to start position
G0 X0 Y0 Z5 F3000

; Draw a 50mm square
M3 S1000 ; Pen down
G1 X50 Y0 F1000 ; Bottom edge
G1 X50 Y50 F1000 ; Right edge
G1 X0 Y50 F1000 ; Top edge
G1 X0 Y0 F1000 ; Left edge
M3 S0 ; Pen up

; Move to center and draw inner square
G0 X12.5 Y12.5 F3000
M3 S1000 ; Pen down
G1 X37.5 Y12.5 F1000 ; Bottom edge
G1 X37.5 Y37.5 F1000 ; Right edge
G1 X12.5 Y37.5 F1000 ; Top edge
G1 X12.5 Y12.5 F1000 ; Left edge
M3 S0 ; Pen up

; Draw center cross
G0 X25 Y12.5 F3000
M3 S1000 ; Pen down
G1 X25 Y37.5 F1000 ; Vertical line
M3 S0 ; Pen up

G0 X12.5 Y25 F3000
M3 S1000 ; Pen down
G1 X37.5 Y25 F1000 ; Horizontal line
M3 S0 ; Pen up

; Return to origin
G0 X0 Y0 Z10 F3000

; End program
M30 ; Program end