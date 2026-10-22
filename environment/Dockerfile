# 基础镜像按补丁版本 + digest 双重锁定；换镜像时用 docker buildx imagetools inspect 取多架构 index digest。
FROM python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 解题与参考解的身份由 task.toml 的 [agent] user = "runner" 指定。
# 不写 USER：Harbor 的保活进程随默认用户运行，评分前清理 runner 进程时不能把它一起结束。
RUN useradd --create-home --uid 1000 runner

WORKDIR /app
COPY app/ /app/
RUN chown -R runner:runner /app
