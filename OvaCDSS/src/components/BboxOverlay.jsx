import React, { useRef, useEffect } from 'react';

export default function BboxOverlay({ imageUrl, bbox, isModal = false }) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  useEffect(() => {
    if (!bbox || !canvasRef.current || !imgRef.current) return;
    const canvas = canvasRef.current;
    const img = imgRef.current;

    const draw = () => {
      const containerW = img.offsetWidth;
      const containerH = img.offsetHeight;
      const naturalW = img.naturalWidth;
      const naturalH = img.naturalHeight;

      if (!containerW || !containerH || !naturalW || !naturalH) return false;

      const scale = Math.min(containerW / naturalW, containerH / naturalH);
      const renderedW = naturalW * scale;
      const renderedH = naturalH * scale;
      const offsetX = (containerW - renderedW) / 2;
      const offsetY = (containerH - renderedH) / 2;

      canvas.width = renderedW;
      canvas.height = renderedH;
      canvas.style.width = renderedW + 'px';
      canvas.style.height = renderedH + 'px';
      canvas.style.left = offsetX + 'px';
      canvas.style.top = offsetY + 'px';

      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const [x1, y1, x2, y2] = bbox;
      const bx = x1 * renderedW;
      const by = y1 * renderedH;
      const bw = (x2 - x1) * renderedW;
      const bh = (y2 - y1) * renderedH;

      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 3;
      ctx.strokeRect(bx, by, bw, bh);
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 14px sans-serif';
      ctx.fillText('종양', bx + 4, by - 6 > 0 ? by - 6 : by + 16);

      return true;
    };

    const drawWithRetry = (attempts = 0) => {
      requestAnimationFrame(() => {
        const success = draw();
        if (!success && attempts < 20) {
          setTimeout(() => drawWithRetry(attempts + 1), 50);
        }
      });
    };

    const observer = new ResizeObserver(() => drawWithRetry());
    observer.observe(img);

    if (img.complete) drawWithRetry();
    else img.onload = () => drawWithRetry();

    return () => observer.disconnect();
  }, [imageUrl, bbox]);

  return (
    <div className="relative w-full" style={{ height: '100%', maxHeight: isModal ? 'none' : '260px' }}>
      <img
        ref={imgRef}
        src={imageUrl}
        alt="AI분석"
        className="w-full h-full object-contain"
      />
      <canvas
        ref={canvasRef}
        className="absolute pointer-events-none"
        style={{ top: 0, left: 0 }}
      />
    </div>
  );
}
