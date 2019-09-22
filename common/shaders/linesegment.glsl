uniform vec2 uScreenSize;
uniform mat4 uMVPMatrix;

uniform vec2 uPos0;
uniform vec2 uPos1;
uniform vec4 uColor0;
uniform vec4 uColor1;
uniform float uWidth;

uniform vec2 uStipple;
uniform float uStippleOffset;

attribute vec2 aWeight;

varying vec4  vPos;
varying float vDist;

/////////////////////////////////////////////////////////////////////////
// vertex shader

#version 130

void main() {
    vec2 d01 = normalize(uPos1 - uPos0);
    vec2 perp = vec2(-d01.y, d01.x);
    float dist = distance(uPos0, uPos1);

    vec2 p =
        (1.0 - aWeight.x) * uPos0 +
        aWeight.x         * uPos1 +
        (aWeight.y - 0.5) * uWidth * perp;
    vPos = uMVPMatrix * vec4(p, 0.0, 1.0);
    vDist = dist * aWeight.x;
    gl_Position = vPos;
}


/////////////////////////////////////////////////////////////////////////
// fragment shader

#version 130

void main() {
    float s = mod(vDist + uStippleOffset, uStipple.x + uStipple.y);
    if(s <= uStipple.x) {
        gl_FragColor = uColor0;
    } else {
        gl_FragColor = uColor1;
        if(uColor1.a <= 0) discard;
    }
}
