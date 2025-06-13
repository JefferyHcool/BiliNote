import * as Icons from '@lobehub/icons';

interface AILogoProps {
    name: string;               // 图标名称（区分大小写！如 OpenAI、DeepSeek）
    style?: 'Color' | 'Text' | 'Outlined' | 'Glyph';
    size?: number;
}

const AILogo = ({ name, style = 'Color', size = 24 }: AILogoProps) => {
    const Icon = Icons[name as keyof typeof Icons];
    if (!Icon) {
        console.error(`❌ 图标组件不存在: ${name}`);
        return <span style={{ fontSize: size }}>🚫</span>;
    }

    const Variant = Icon[style as keyof typeof Icon];
    if (!Variant) {
        return <Icon size={size} />;
    }

    return <Variant size={size} />;
};

export default AILogo;