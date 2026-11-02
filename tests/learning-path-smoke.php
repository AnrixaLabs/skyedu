<?php
/** Minimal WordPress stubs to smoke-test shortcode HTML without deployment. */
define('ABSPATH', __DIR__);
$GLOBALS['shortcode'] = [];
$GLOBALS['enqueue'] = [];
$GLOBALS['locale'] = 'en_US';
function add_shortcode($name, $callback) { $GLOBALS['shortcode'][$name] = $callback; }
function shortcode_atts($defaults, $atts, $name) { return array_merge($defaults, $atts); }
function get_locale() { return $GLOBALS['locale']; }
function wp_parse_url($url, $component = -1) { return parse_url($url, $component); }
function plugins_url($url, $file) { return 'https://example.org/wp-content/plugins/skyed-learning-path/' . $url; }
function wp_enqueue_style($name, $url, $dependencies, $version) { $GLOBALS['enqueue'][] = $url; }
function wp_enqueue_script($name, $url, $dependencies, $version, $footer) { $GLOBALS['enqueue'][] = $url; }
function wp_unique_id($prefix) { static $n = 0; return $prefix . ++$n; }
function esc_html($text) { return htmlspecialchars((string)$text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function esc_attr($text) { return esc_html($text); }
require __DIR__ . '/../wp_plugin/skyed-learning-path/skyed-learning-path.php';
function check($condition, $message) { if (!$condition) { throw new RuntimeException($message); } }
check(isset($GLOBALS['shortcode']['skyed_learning_path']), 'Shortcode must be registered');
$render = $GLOBALS['shortcode']['skyed_learning_path'];
$english = $render(['lang' => 'en']);
$chinese = $render(['lang' => 'zh']);
check(strpos($english, 'Build a practical English learning routine') !== false, 'English title');
check(strpos($chinese, '为孩子制定适合自己的英语学习计划') !== false, 'Chinese title');
check(substr_count($english, '<select') === 4, 'Expected four input groups');
check(strpos($chinese, 'data-lang="zh"') !== false, 'Chinese language metadata');
check(strpos($english, 'data-lang="en"') !== false, 'English language metadata');
$_SERVER['REQUEST_URI'] = '/zh/tools/';
check(strpos($render([]), 'data-lang="zh"') !== false, 'Chinese URL locale inference');
$_SERVER['REQUEST_URI'] = '/en/tools/';
check(strpos($render([]), 'data-lang="en"') !== false, 'English URL locale inference');
check(count($GLOBALS['enqueue']) >= 2, 'Assets enqueued');
check(strpos($render(['lang' => '" onmouseover="alert(1)']), 'onmouseover=') === false, 'Invalid language sanitized');
echo "SKYED_BILINGUAL_SHORTCODE_SMOKE=PASS\n";
