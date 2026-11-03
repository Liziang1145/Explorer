#version 450

layout(location = 0) out vec4 outColor;
layout(location = 0) in vec4 v_color;
void main() {
   float fakeTime = gl_FragCoord.x * 0.01; 
    float glow = 0.5 + 0.5 * sin(fakeTime);
    outColor = v_color;
}