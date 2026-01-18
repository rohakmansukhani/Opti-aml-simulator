import Image from 'next/image';

interface LogoProps {
    className?: string;
    width?: number;
    height?: number;
}

export function Logo({ className, width = 48, height = 48 }: LogoProps) {
    return (
        <div className={`flex items-center gap-3 ${className}`}>
            <Image
                src="/logo.png"
                alt="SecureCore Logo"
                width={width}
                height={height}
                className="rounded-lg shadow-sm"
            />
            <span className="font-bold text-xl tracking-tight text-slate-900">
                SecureCore
            </span>
        </div>
    );
}
