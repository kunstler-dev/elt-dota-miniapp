/** Hero scene dimensions, shared by HeroStage (main chunk) and Character3D (three.js chunk).
 *  The canvas is larger than the tap stage so the hook, cleaver and future arcana effects aren't clipped. */
export const STAGE_SIZE = 300
export const CANVAS_H = 470
/** Camera distance grows with canvas height, so Pudge appears the same size as at 300 px and 4.6 */
export const CAMERA_DIST = (4.6 * CANVAS_H) / STAGE_SIZE
