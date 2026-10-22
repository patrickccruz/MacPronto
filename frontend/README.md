# Interface do MacPronto

React + TypeScript + Tailwind + shadcn/ui, exibida pelo pywebview (Edge WebView2).

```powershell
npm install
npm run build        # gera dist/, que o MacPronto carrega
npm run dev          # servidor de desenvolvimento em http://localhost:5173
```

Para usar o servidor de desenvolvimento dentro da janela do MacPronto:

```powershell
$env:MACPRONTO_DEV_URL = "http://localhost:5173"
python -m macpronto --debug
```

Num navegador comum, sem o Python, a interface entra no modo de demonstração com os
dados de `src/mocks` (gerados por `scripts/make_ui_mocks.py`). Parâmetros úteis na URL:
`?mock=laptop`, `&accepted`, `&loaded`, `&view=report`, `&theme=light`.
