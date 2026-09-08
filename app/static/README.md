# Convenções do frontend

Os nomes descrevem a função do componente, sem incluir o nome do projeto:

- Layout: `app-page`, `app-layout`, `main-wrapper` e `main-content`.
- Navegação: `sidebar`, `sidebar__item`, `sidebar__item--prominent` e `mobile-header`.
- Login: `login-page`, `login-form`, `login-field` e `login-field--error`.
- Componentes compartilhados: `summary-card`, `card-heading` e `app-toast`.

Use `componente__elemento` para partes de um componente, `componente--variacao`
para variações e `is-*` para estados, como `is-open`. Mantenha os nomes já
genéricos ao reaproveitar componentes.

As variáveis básicas usam `--ui-*`, como `--ui-blue-600`. Os componentes podem
usar as variáveis semânticas de `css/colors.css`, como `--color-primary` e
`--color-surface`, que também definem os temas claro e escuro.

Use atributos `data-*` para os controles JavaScript, como `data-app-layout` e
`data-login-form`. Ao renomear classes, atualize também os seletores e as classes
geradas pelos scripts. IDs e atributos `aria-controls` devem continuar associados.

As classes `fa-*` pertencem ao Font Awesome. As fontes são carregadas por
`vendor/fontawesome/css/font-bindings.css`.

As chaves existentes de `localStorage` foram preservadas para manter o tema,
o estado do menu e o usuário lembrado. Elas não são classes CSS nem precisam
ser renomeadas ao reutilizar o visual.
