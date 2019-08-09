uniform mat4 uMVPMatrix;
uniform vec2 screen_size;

uniform float left;
uniform float right;
uniform float top;
uniform float bottom;

uniform float margin_left;
uniform float margin_right;
uniform float margin_top;
uniform float margin_bottom;

uniform float padding_left;
uniform float padding_right;
uniform float padding_top;
uniform float padding_bottom;

uniform float border_width;
uniform float border_radius;
uniform vec4  border_left_color;
uniform vec4  border_right_color;
uniform vec4  border_top_color;
uniform vec4  border_bottom_color;

uniform vec4  background_color;

uniform float using_image;
uniform sampler2D image;

attribute vec2 pos;

varying vec2 screen_pos;

/////////////////////////////////////////////////////////////////////////
// vertex shader

#version 120

void main() {
    // set vertex to bottom-left, top-left, top-right, or bottom-right location, depending on pos
    vec2 p = vec2(left, bottom);
    if(pos.x > 0.5) p.x = right;
    if(pos.y > 0.5) p.y = top;

    screen_pos  = p;
    gl_Position = uMVPMatrix * vec4(p, 0, 1);
}


/////////////////////////////////////////////////////////////////////////
// fragment shader

#version 120

int get_region() {
    /* return values:
          0 - outside border region
          1 - top border
          2 - right border
          3 - bottom border
          4 - left border
          5 - inside border region
         -1 - ERROR (should never happen)
    */

    float dist_left   = screen_pos.x - (left + margin_left);
    float dist_right  = (right - margin_right) - screen_pos.x;
    float dist_bottom = screen_pos.y - (bottom + margin_bottom);
    float dist_top    = (top - margin_top) - screen_pos.y;
    float radwid = max(border_radius, border_width);
    float rad = max(0, border_radius - border_width);
    float radwid2 = radwid * radwid, rad2 = rad * rad;
    float r2;

    // outside
    if(dist_left < 0 || dist_right < 0 || dist_bottom < 0 || dist_top < 0) return 0;

    // within top and bottom, might be left or right side
    if(dist_bottom > radwid && dist_top > radwid) {
        if(dist_left > border_width && dist_right > border_width) return 5;
        return (dist_left < dist_right) ? 4 : 2;
    }

    // within left and right, might be bottom or top
    if(dist_left > radwid && dist_right > radwid) {
        if(dist_bottom > border_width && dist_top > border_width) return 5;
        return (dist_bottom < dist_top) ? 3 : 1;
    }

    // top-left
    if(dist_top <= radwid && dist_left <= radwid) {
        r2 = pow(dist_left - radwid, 2.0) + pow(dist_top - radwid, 2.0);
        if(r2 > radwid2) return 0;
        if(r2 < rad2) return 5;
        return (dist_left < dist_top) ? 4 : 1;
    }
    // top-right
    if(dist_top <= radwid && dist_right <= radwid) {
        r2 = pow(dist_right - radwid, 2.0) + pow(dist_top - radwid, 2.0);
        if(r2 > radwid2) return 0;
        if(r2 < rad2) return 5;
        return (dist_right < dist_top) ? 2 : 1;
    }
    // bottom-left
    if(dist_bottom <= radwid && dist_left <= radwid) {
        r2 = pow(dist_left - radwid, 2.0) + pow(dist_bottom - radwid, 2.0);
        if(r2 > radwid2) return 0;
        if(r2 < rad2) return 5;
        return (dist_left < dist_bottom) ? 4 : 3;
    }
    // bottom-right
    if(dist_bottom <= radwid && dist_right <= radwid) {
        r2 = pow(dist_right - radwid, 2.0) + pow(dist_bottom - radwid, 2.0);
        if(r2 > radwid2) return 0;
        if(r2 < rad2) return 5;
        return (dist_right < dist_bottom) ? 2 : 3;
    }

    // something bad happened
    return -1;
}

vec2 get_texcoord() {
    float w = (right - left) - (margin_left + border_width + padding_left + padding_right + border_width + margin_right);
    float h = (top - bottom) - (margin_top + border_width + padding_top + padding_bottom + border_width + margin_bottom);
    float tx = (screen_pos.x - (left + margin_left + border_width + padding_left)) / w;
    float ty = (screen_pos.y - (bottom + margin_bottom + border_width + padding_bottom)) / h;
    return vec2(tx, 1.0 - ty);
}

void main() {
    int region = get_region();
    if(region == 5) {
        vec4 c = background_color;
        if(using_image > 0.5) {
            vec2 texcoord = get_texcoord();
            if(texcoord.x >= 0 && texcoord.x <= 1 && texcoord.y >= 0 && texcoord.y <= 1) {
                vec4 t = texture(image, texcoord);
                float a = t.a + c.a * (1.0 - t.a);
                c = vec4((t.rgb * t.a + c.rgb * c.a * (1.0 - t.a)) / a, a);
            }
        }
        gl_FragColor = c;
    }
    else if(region == 1) gl_FragColor = border_top_color;
    else if(region == 2) gl_FragColor = border_right_color;
    else if(region == 3) gl_FragColor = border_bottom_color;
    else if(region == 4) gl_FragColor = border_left_color;
    else discard;
}
