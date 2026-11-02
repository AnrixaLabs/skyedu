<?php
/**
 * Plugin Name: SkyEd Bilingual Learning Path
 * Description: Privacy-first, bilingual family English-learning planner.
 * Version: 1.0.0
 * Requires PHP: 7.4
 * Author: Sky Education
 * License: Proprietary
 */
if (!defined('ABSPATH')) { exit; }

final class SkyEd_Learning_Path {
    private const VERSION = '1.0.0';
    private const SHORTCODE = 'skyed_learning_path';

    public static function init(): void {
        add_shortcode(self::SHORTCODE, [self::class, 'render']);
        add_action('wp_enqueue_scripts', [self::class, 'enqueue_if_needed']);
    }

    /** Enqueue styles before WordPress prints the page header. */
    public static function enqueue_if_needed(): void {
        if (!is_singular()) { return; }
        $post = get_post();
        if ($post && isset($post->post_content) && has_shortcode((string)$post->post_content, self::SHORTCODE)) {
            self::enqueue_assets();
        }
    }

    private static function enqueue_assets(): void {
        wp_enqueue_style('skyed-learning-path', plugins_url('assets/learning-path.css', __FILE__), [], self::VERSION);
        wp_enqueue_script('skyed-learning-path', plugins_url('assets/learning-path.js', __FILE__), [], self::VERSION, true);
    }

    private static function language(string $requested): string {
        $requested = strtolower(trim($requested));
        if (in_array($requested, ['zh', 'en'], true)) { return $requested; }
        $path = (string)wp_parse_url((string)($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
        if (preg_match('#^/zh(?:/|$)#i', $path)) { return 'zh'; }
        if (preg_match('#^/en(?:/|$)#i', $path)) { return 'en'; }
        return strpos(strtolower((string)get_locale()), 'zh') === 0 ? 'zh' : 'en';
    }

    private static function copy(string $lang): array {
        $data = [
            'en' => [
                'eyebrow' => 'SKY EDUCATION · FAMILY LEARNING TOOL',
                'title' => 'Build a practical English learning routine',
                'intro' => 'Choose your child’s age, current comfort level and main goal. Receive a four-week activity outline you can adapt at home.',
                'age' => 'Age group', 'level' => 'Current English experience',
                'goal' => 'Main learning goal', 'minutes' => 'Time per session',
                'choose' => 'Please select', 'a34' => '3–4 years',
                'a56' => '5–6 years', 'a79' => '7–9 years',
                'new' => 'Just getting started', 'words' => 'Understands familiar words',
                'sentences' => 'Uses short sentences',
                'listening' => 'Listening and understanding',
                'speaking' => 'Speaking with confidence',
                'reading' => 'Early reading and stories',
                'button' => 'Create my learning plan',
                'privacy' => 'No name, email or recording required. Your selections stay in this browser session and are not sent to Sky Education.',
                'noscript' => 'Enable JavaScript to generate the interactive plan.',
            ],
            'zh' => [
                'eyebrow' => '思恺教育 · 家庭学习工具',
                'title' => '为孩子制定适合自己的英语学习计划',
                'intro' => '选择孩子的年龄、当前英语基础和主要学习目标，即可生成一份可根据家庭实际情况调整的四周活动建议。',
                'age' => '孩子的年龄', 'level' => '目前的英语基础',
                'goal' => '最希望加强的方面', 'minutes' => '每次练习时间',
                'choose' => '请选择', 'a34' => '3—4岁',
                'a56' => '5—6岁', 'a79' => '7—9岁',
                'new' => '刚开始接触英语', 'words' => '能听懂一些常见单词',
                'sentences' => '能使用简单句子',
                'listening' => '听力理解', 'speaking' => '口语表达',
                'reading' => '阅读与故事理解',
                'button' => '生成家庭学习计划',
                'privacy' => '无需填写姓名、邮箱或上传录音。所选内容仅在当前浏览器页面中使用，不会发送给思恺教育。',
                'noscript' => '请启用 JavaScript 以生成互动学习计划。',
            ],
        ];
        return $data[$lang];
    }

    public static function render($attributes = []): string {
        $atts = shortcode_atts(['lang' => 'auto'], (array)$attributes, self::SHORTCODE);
        $lang = self::language((string)$atts['lang']);
        $t = self::copy($lang);
        // Fallback for dynamically rendered shortcodes outside post_content.
        self::enqueue_assets();
        $id = function_exists('wp_unique_id') ? wp_unique_id('skyed-path-') : uniqid('skyed-path-');
        $options = [
            'age' => ['a34', 'a56', 'a79'],
            'level' => ['new', 'words', 'sentences'],
            'goal' => ['listening', 'speaking', 'reading'],
            'minutes' => ['10', '15', '20'],
        ];
        ob_start(); ?>
        <section class="skyed-path" data-skyed-learning-path data-lang="<?php echo esc_attr($lang); ?>" lang="<?php echo esc_attr($lang === 'zh' ? 'zh-CN' : 'en'); ?>" aria-labelledby="<?php echo esc_attr($id); ?>-title">
            <div class="skyed-path__hero">
                <div class="skyed-path__eyebrow"><?php echo esc_html($t['eyebrow']); ?></div>
                <h2 id="<?php echo esc_attr($id); ?>-title"><?php echo esc_html($t['title']); ?></h2>
                <p><?php echo esc_html($t['intro']); ?></p>
            </div>
            <form class="skyed-path__form">
                <div class="skyed-path__fields">
                    <?php foreach ($options as $field => $values): ?>
                        <div class="skyed-path__field">
                            <label for="<?php echo esc_attr($id . '-' . $field); ?>"><?php echo esc_html($t[$field]); ?></label>
                            <select id="<?php echo esc_attr($id . '-' . $field); ?>" name="<?php echo esc_attr($field); ?>" required>
                                <option value="" disabled selected><?php echo esc_html($t['choose']); ?></option>
                                <?php foreach ($values as $value): ?>
                                    <option value="<?php echo esc_attr($value); ?>"><?php echo esc_html($field === 'minutes' ? $value . ($lang === 'zh' ? '分钟' : ' minutes') : $t[$value]); ?></option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                    <?php endforeach; ?>
                </div>
                <button class="skyed-path__submit" type="submit"><?php echo esc_html($t['button']); ?></button>
                <p class="skyed-path__privacy"><?php echo esc_html($t['privacy']); ?></p>
            </form>
            <section class="skyed-path__result" aria-live="polite" aria-atomic="true" hidden tabindex="-1"></section>
            <noscript><p><?php echo esc_html($t['noscript']); ?></p></noscript>
        </section>
        <?php return (string)ob_get_clean();
    }
}
SkyEd_Learning_Path::init();
