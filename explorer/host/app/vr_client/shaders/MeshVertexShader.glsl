#version 450

layout(std140, binding = 0) uniform CameraConstants {
    mat4 viewProj;
    mat4 view;          
    uvec4 padding;
};

layout(location = 0) in vec4 a_Positions;
layout(location = 0) out vec4 v_color;

void main() {
    // vec4 worldPos = vec4(a_Positions.xyz, 1.0);
    // gl_Position = viewProj * a_Positions;

    gl_Position = a_Positions;
    // gl_Position = a_Positions + vec4(viewportSize.x * 0.001, 0.0, 0.0, 0.0);
    gl_Position = viewProj * a_Positions;

    if(padding[1]>0)
    {
        v_color=vec4(0.0f, 1.0f, 0.0f, 1.0f);
    }
    else
    {
        v_color=vec4(1.0f, 1.0f, 1.0f, 1.0f);
    }

}


// void main() {
//        const vec4 pos[3] = vec4[3](
//         vec4(0.0, -0.5, 0.0, 1.0),
//         vec4(0.5, 0.5, 0.0, 1.0),
//         vec4(-0.5, 0.5, 0.0, 1.0)
//     );
//     gl_Position = pos[gl_VertexIndex];
// }

