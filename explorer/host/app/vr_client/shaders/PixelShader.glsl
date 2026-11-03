#version 450 core



layout(std430, binding = 3) readonly buffer Norms {
    vec4 norm[]; // norm
};

layout(location = 0) in vec4 v_Light;
layout(location = 1) in vec4 v_worldPos;
layout(location = 2) in vec4 v_color;
layout(location = 3) in flat float v_realPointSize;
layout(location = 4) in flat float v_pointSize;
layout(location = 0) out vec4 fragColor;


void main()
{
    vec2 uv = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(uv, uv);
    if(r2 > 1.0)
        discard;
    // vec3 color_light = vec3(0.9f, 0.9f, 0.9f);
    // vec3 color_dark = vec3(0.4f, 0.4f, 0.4f);
    vec3 color_light = v_color.xyz;
    vec3 color_dark = v_color.xyz * 0.4;
    fragColor = vec4(color_light, v_color[3]);
    // if(v_pointSize > 4.0f)
    // {
    //     float z = sqrt(1.0 - r2);
    //     vec3 sphereNormal = normalize(vec3(uv, z));
    //     vec3 uvInWorld = v_worldPos.xyz + sphereNormal * v_realPointSize;

    //     float t = smoothstep(-0.2, 0.2, dot(normalize(uvInWorld), normalize(v_Light.xyz)));
    //     vec3 baseColor = mix(color_light, color_dark, t);
    
    //     float alpha = smoothstep(1.0, 0.8, r2);
    //     fragColor = vec4(baseColor, alpha);
    // }
    // else
    // {
    //     fragColor = vec4(color_light, 0.8);
    // }
}

