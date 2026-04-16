update users
set tenant_id = (select id from tenants where slug = 'platform-admin' limit 1),
    email = 'admin@soservices.com.br',
    full_name = 'Administrador SOServices',
    role = 'superadmin',
    active = true
where id = (
    select id from users where username = 'admin' and role = 'superadmin' order by created_at limit 1
);
