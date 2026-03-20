import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
    Server,
    Cpu,
    AudioLines,
    Film,
    RefreshCw,
    CheckCircle2,
    XCircle,
    Loader2
} from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { getDeployStatus, DeployStatus } from '@/services/system'

export default function Monitor() {
    const [status, setStatus] = useState<DeployStatus | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

    const fetchStatus = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const data = await getDeployStatus()
            setStatus(data)
            setLastUpdated(new Date())
        } catch (err) {
            setError('无法连接到后端服务')
            setStatus(null)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchStatus()
        // 自动刷新（每 30 秒）
        const interval = setInterval(fetchStatus, 30000)
        return () => clearInterval(interval)
    }, [fetchStatus])

    const StatusBadge = ({ ok, label }: { ok: boolean; label?: string }) => (
        <Badge
            variant={ok ? 'default' : 'destructive'}
            className={ok ? 'bg-green-500 hover:bg-green-600' : ''}
        >
            {ok ? (
                <><CheckCircle2 className="mr-1 h-3 w-3" />{label || '正常'}</>
            ) : (
                <><XCircle className="mr-1 h-3 w-3" />{label || '异常'}</>
            )}
        </Badge>
    )

    return (
        <ScrollArea className="h-full overflow-y-auto bg-white">
            <div className="container mx-auto px-4 py-8">
                {/* Header */}
                <div className="mb-8 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold">部署监控</h1>
                        <p className="text-muted-foreground text-sm">
                            实时监控系统各组件运行状态
                        </p>
                    </div>
                    <div className="flex items-center gap-4">
                        {lastUpdated && (
                            <span className="text-muted-foreground text-xs">
                                最后更新: {lastUpdated.toLocaleTimeString()}
                            </span>
                        )}
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={fetchStatus}
                            disabled={loading}
                        >
                            {loading ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="mr-2 h-4 w-4" />
                            )}
                            刷新
                        </Button>
                    </div>
                </div>

                {error && (
                    <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
                        {error}
                    </div>
                )}

                {/* Status Cards */}
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    {/* Backend FastAPI */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-lg font-medium">
                                <Server className="mr-2 inline h-5 w-5 text-blue-500" />
                                后端 FastAPI
                            </CardTitle>
                            {status && <StatusBadge ok={status.backend.status === 'running'} label="运行中" />}
                        </CardHeader>
                        <CardContent>
                            {loading && !status ? (
                                <div className="flex items-center gap-2 text-gray-500">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    加载中...
                                </div>
                            ) : status ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">状态:</span>
                                        <span className={status.backend.status === 'running' ? 'font-medium text-green-600' : 'font-medium text-red-600'}>
                                            {status.backend.status === 'running' ? '运行中' : status.backend.status}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">端口:</span>
                                        <span className="font-mono">{status.backend.port}</span>
                                    </div>
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>

                    {/* CUDA GPU */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-lg font-medium">
                                <Cpu className="mr-2 inline h-5 w-5 text-green-500" />
                                CUDA GPU
                            </CardTitle>
                            {status && <StatusBadge ok={status.cuda.available} label={status.cuda.available ? '已启用' : '未启用'} />}
                        </CardHeader>
                        <CardContent>
                            {loading && !status ? (
                                <div className="flex items-center gap-2 text-gray-500">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    加载中...
                                </div>
                            ) : status ? (
                                <div className="space-y-2 text-sm">
                                    {status.cuda.available ? (
                                        <>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">GPU:</span>
                                                <span className="font-medium">{status.cuda.gpu_name}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">CUDA 版本:</span>
                                                <span className="font-mono">{status.cuda.version}</span>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-muted-foreground">
                                            CUDA 不可用，将使用 CPU 模式
                                        </div>
                                    )}
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>

                    {/* Whisper Model */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-lg font-medium">
                                <AudioLines className="mr-2 inline h-5 w-5 text-purple-500" />
                                Whisper 模型
                            </CardTitle>
                            {status && <StatusBadge ok={true} label="已配置" />}
                        </CardHeader>
                        <CardContent>
                            {loading && !status ? (
                                <div className="flex items-center gap-2 text-gray-500">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    加载中...
                                </div>
                            ) : status ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">模型大小:</span>
                                        <span className="font-medium">{status.whisper.model_size}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">转写引擎:</span>
                                        <span className="font-mono">{status.whisper.transcriber_type}</span>
                                    </div>
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>

                    {/* FFmpeg */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-lg font-medium">
                                <Film className="mr-2 inline h-5 w-5 text-orange-500" />
                                FFmpeg
                            </CardTitle>
                            {status && <StatusBadge ok={status.ffmpeg.available} label={status.ffmpeg.available ? '可用' : '不可用'} />}
                        </CardHeader>
                        <CardContent>
                            {loading && !status ? (
                                <div className="flex items-center gap-2 text-gray-500">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    加载中...
                                </div>
                            ) : status ? (
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">状态:</span>
                                        <span className={status.ffmpeg.available ? 'font-medium text-green-600' : 'font-medium text-red-600'}>
                                            {status.ffmpeg.available ? '已安装' : '未安装'}
                                        </span>
                                    </div>
                                    {!status.ffmpeg.available && (
                                        <div className="text-xs text-red-500">
                                            请安装 FFmpeg 并添加到系统 PATH
                                        </div>
                                    )}
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>
                </div>

                {/* Footer Info */}
                <div className="mt-8 text-center text-xs text-gray-400">
                    状态每 30 秒自动刷新
                </div>
            </div>
        </ScrollArea>
    )
}
