import * as Icons from '@lobehub/icons';

interface AILogoProps {
    name: string;               // 图标名称（区分大小写！如 OpenAI、DeepSeek）
    style?: 'Color' | 'Text' | 'Outlined' | 'Glyph';
    size?: number;
}

const AILogo = ({ name, style = 'Color', size = 24 }: AILogoProps) => {
    const Icon = name ? Icons[name as keyof typeof Icons] : undefined;
    if (!Icon) {
        if (name && name !== 'custom') {
            console.warn(`AILogo: 未匹配到图标，使用占位: ${name}`);
        }
        return <span style={{ fontSize: size }}>🚫</span>;
    }

    const Variant = Icon[style as keyof typeof Icon];
    if (!Variant) {
        return <Icon size={size} />;
    }

    return <Variant size={size} />;
};

export default AILogo;