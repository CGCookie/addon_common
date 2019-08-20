uniform mat4 uMVPMatrix;
uniform vec2 screen_size;

uniform float left;
uniform float right;
uniform float top;
uniform float bottom;
uniform float width;
uniform float height;

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

const bool DEBUG = false;
const bool DEBUG_CHECKER = true;

const int REGION_OUTSIDE_LEFT   = -4;
const int REGION_OUTSIDE_BOTTOM = -3;
const int REGION_OUTSIDE_RIGHT  = -2;
const int REGION_OUTSIDE_TOP    = -1;
const int REGION_OUTSIDE        = 0;
const int REGION_BORDER_TOP     = 1;
const int REGION_BORDER_RIGHT   = 2;
const int REGION_BORDER_BOTTOM  = 3;
const int REGION_BORDER_LEFT    = 4;
const int REGION_BACKGROUND     = 5;
const int REGION_ERROR          = -100;

/////////////////////////////////////////////////////////////////////////
// vertex shader

#version 120

void main() {
    // set vertex to bottom-left, top-left, top-right, or bottom-right location, depending on pos
    vec2 p = vec2(
        (pos.x < 0.5) ? (left   - 1) : (right + 1),
        (pos.y < 0.5) ? (bottom - 1) : (top   + 1)
    );

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
    float dist_right  = (right - margin_right + 1) - screen_pos.x;
    float dist_bottom = screen_pos.y - (bottom + margin_bottom - 1);
    float dist_top    = (top - margin_top) - screen_pos.y;
    float radwid  = max(border_radius, border_width);
    float rad     = max(0, border_radius - border_width);
    float radwid2 = radwid * radwid;
    float rad2    = rad * rad;
    float r2;

    // outside
    float dist_min = min(min(min(dist_left, dist_right), dist_top), dist_bottom);
    if(dist_min < 0) {
        if(dist_min == dist_left)   return REGION_OUTSIDE_LEFT;
        if(dist_min == dist_right)  return REGION_OUTSIDE_RIGHT;
        if(dist_min == dist_top)    return REGION_OUTSIDE_TOP;
        if(dist_min == dist_bottom) return REGION_OUTSIDE_BOTTOM;
        return REGION_ERROR;
    }

    // within top and bottom, might be left or right side
    if(dist_bottom > radwid && dist_top > radwid) {
        if(dist_left > border_width && dist_right > border_width) return REGION_BACKGROUND;
        if(dist_left < dist_right) return REGION_BORDER_LEFT;
        return REGION_BORDER_RIGHT;
    }

    // within left and right, might be bottom or top
    if(dist_left > radwid && dist_right > radwid) {
        if(dist_bottom > border_width && dist_top > border_width) return REGION_BACKGROUND;
        if(dist_bottom < dist_top) return REGION_BORDER_BOTTOM;
        return REGION_BORDER_TOP;
    }

    // top-left
    if(dist_top <= radwid && dist_left <= radwid) {
        r2 = pow(dist_left - radwid, 2.0) + pow(dist_top - radwid, 2.0);
        if(r2 > radwid2)             return REGION_OUTSIDE;
        if(r2 < rad2)                return REGION_BACKGROUND;
        if(dist_left < dist_top)     return REGION_BORDER_LEFT;
        return REGION_BORDER_TOP;
    }
    // top-right
    if(dist_top <= radwid && dist_right <= radwid) {
        r2 = pow(dist_right - radwid, 2.0) + pow(dist_top - radwid, 2.0);
        if(r2 > radwid2)             return REGION_OUTSIDE;
        if(r2 < rad2)                return REGION_BACKGROUND;
        if(dist_right < dist_top)    return REGION_BORDER_RIGHT;
        return REGION_BORDER_TOP;
    }
    // bottom-left
    if(dist_bottom <= radwid && dist_left <= radwid) {
        r2 = pow(dist_left - radwid, 2.0) + pow(dist_bottom - radwid, 2.0);
        if(r2 > radwid2)             return REGION_OUTSIDE;
        if(r2 < rad2)                return REGION_BACKGROUND;
        if(dist_left < dist_bottom)  return REGION_BORDER_LEFT;
        return REGION_BORDER_BOTTOM;
    }
    // bottom-right
    if(dist_bottom <= radwid && dist_right <= radwid) {
        r2 = pow(dist_right - radwid, 2.0) + pow(dist_bottom - radwid, 2.0);
        if(r2 > radwid2)             return REGION_OUTSIDE;
        if(r2 < rad2)                return REGION_BACKGROUND;
        if(dist_right < dist_bottom) return REGION_BORDER_RIGHT;
        return REGION_BORDER_BOTTOM;
    }

    // something bad happened
    return REGION_ERROR;
}

vec4 mix_image(vec4 bg) {
    vec4 c = bg;
    float w = width  - (margin_left + border_width + padding_left + padding_right  + border_width + margin_right);
    float h = height - (margin_top  + border_width + padding_top  + padding_bottom + border_width + margin_bottom);
    float tx = screen_pos.x - (left + (margin_left + border_width + padding_left));
    float ty = screen_pos.y - (top  - (margin_top  + border_width + padding_top));
    vec2 texcoord = vec2(tx / (w), -ty / (h));
    if((0 <= texcoord.x && texcoord.x < 1) && (0 <= texcoord.y && texcoord.y < 1)) {
        vec4 t = texture(image, texcoord);
        float a = t.a + c.a * (1.0 - t.a);
        c = vec4((t.rgb * t.a + c.rgb * c.a * (1.0 - t.a)) / a, a);

        if(DEBUG && DEBUG_CHECKER) {
            int i = (int(32 * texcoord.x) + 4 * int(32 * texcoord.y)) % 16;
                 if(i ==  0) c = vec4(0.0, 0.0, 0.0, 1);
            else if(i ==  1) c = vec4(0.0, 0.0, 0.5, 1);
            else if(i ==  2) c = vec4(0.0, 0.5, 0.0, 1);
            else if(i ==  3) c = vec4(0.0, 0.5, 0.5, 1);
            else if(i ==  4) c = vec4(0.5, 0.0, 0.0, 1);
            else if(i ==  5) c = vec4(0.5, 0.0, 0.5, 1);
            else if(i ==  6) c = vec4(0.5, 0.5, 0.0, 1);
            else if(i ==  7) c = vec4(0.5, 0.5, 0.5, 1);
            else if(i ==  8) c = vec4(0.3, 0.3, 0.3, 1);
            else if(i ==  9) c = vec4(0.0, 0.0, 1.0, 1);
            else if(i == 10) c = vec4(0.0, 1.0, 0.0, 1);
            else if(i == 11) c = vec4(0.0, 1.0, 1.0, 1);
            else if(i == 12) c = vec4(1.0, 0.0, 0.0, 1);
            else if(i == 13) c = vec4(1.0, 0.0, 1.0, 1);
            else if(i == 14) c = vec4(1.0, 1.0, 0.0, 1);
            else if(i == 15) c = vec4(1.0, 1.0, 1.0, 1);
        }
    } else if(DEBUG) {
        // vec4 t = vec4(0,1,1,0.50);
        // float a = t.a + c.a * (1.0 - t.a);
        // c = vec4((t.rgb * t.a + c.rgb * c.a * (1.0 - t.a)) / a, a);
        c = vec4(
            1.0 - (1.0 - c.r) * 0.5,
            1.0 - (1.0 - c.g) * 0.5,
            1.0 - (1.0 - c.b) * 0.5,
            c.a
            );
    }
    return c;
}

void main() {
    vec4 c = vec4(0,0,0,0);
    int region = get_region();
         if(region == REGION_OUTSIDE_TOP)    { c = vec4(1,0,0,0.25); if(!DEBUG) discard; }
    else if(region == REGION_OUTSIDE_RIGHT)  { c = vec4(0,1,0,0.25); if(!DEBUG) discard; }
    else if(region == REGION_OUTSIDE_BOTTOM) { c = vec4(0,0,1,0.25); if(!DEBUG) discard; }
    else if(region == REGION_OUTSIDE_LEFT)   { c = vec4(0,1,1,0.25); if(!DEBUG) discard; }
    else if(region == REGION_OUTSIDE)        { c = vec4(1,1,0,0.25); if(!DEBUG) discard; }
    else if(region == REGION_BORDER_TOP)       c = border_top_color;
    else if(region == REGION_BORDER_RIGHT)     c = border_right_color;
    else if(region == REGION_BORDER_BOTTOM)    c = border_bottom_color;
    else if(region == REGION_BORDER_LEFT)      c = border_left_color;
    else if(region == REGION_BACKGROUND)       c = background_color;
    else if(region == REGION_ERROR)            c = vec4(1,0,0,1);  // should never hit here
    else                                       c = vec4(1,0,1,1);  // should really never hit here
    if(using_image > 0.5) c = mix_image(c);
    gl_FragColor = c;
}
