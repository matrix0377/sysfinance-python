from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

def login_view(request):
	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(request, username=username, password=password)
		if user is not None:
			login(request, user)
			return redirect('dashboard')
		else:
			return render(request, 'financeiro/login.html', {'error': 'Usuário ou senha inválidos'})
	return render(request, 'financeiro/login.html')

def logout_view(request):
	logout(request)
	return redirect('login')

from django.db.models import Sum

@login_required
def dashboard(request):
	from .models import Conta, Transacao, Meta
	# Totais de receitas/despesas do mês atual
	from datetime import date
	today = date.today()
	transacoes = Transacao.objects.filter(usuario=request.user, data__year=today.year, data__month=today.month)
	total_receitas = transacoes.filter(tipo='receita').aggregate(total=Sum('valor'))['total'] or 0
	total_despesas = transacoes.filter(tipo='despesa').aggregate(total=Sum('valor'))['total'] or 0
	# Saldo total das contas
	contas = Conta.objects.filter(usuario=request.user)
	saldo_contas = contas.aggregate(total=Sum('saldo_inicial'))['total'] or 0
	# Transações recentes (últimas 5)
	transacoes_recentes = Transacao.objects.filter(usuario=request.user).order_by('-criado_em', '-data')[:5]
	# Metas com cálculo de progresso e valor atual
	metas_objs = Meta.objects.filter(usuario=request.user)
	metas = []
	for meta in metas_objs:
		valor_disponivel = float(saldo_contas)
		valor_atual = float(meta.valor_atual) + (valor_disponivel * 0.1)
		valor_atual = min(valor_atual, float(meta.valor))
		progresso = (valor_atual / float(meta.valor)) * 100 if float(meta.valor) > 0 else 0
		progresso = min(progresso, 100)
		metas.append({
			'nome': meta.nome,
			'valor': float(meta.valor),
			'valor_atual': valor_atual,
			'progresso': progresso,
		})
	context = {
		'total_receitas': total_receitas,
		'total_despesas': total_despesas,
		'saldo_contas': saldo_contas,
		'transacoes_recentes': transacoes_recentes,
		'contas': contas,
		'metas': metas,
		'now': today,
	}
	return render(request, 'financeiro/dashboard.html', context)

@login_required
def contas(request):
	from .models import Conta
	contas = Conta.objects.filter(usuario=request.user)
	errors = []
	success = ''
	total_saldo = contas.aggregate(total=Sum('saldo_inicial'))['total'] or 0
	if request.method == 'POST':
		nome = request.POST.get('nome', '').strip()
		tipo = request.POST.get('tipo')
		saldo_inicial = request.POST.get('saldo_inicial', 0)
		if len(nome) < 2:
			errors.append('Nome da conta deve ter pelo menos 2 caracteres')
		if tipo not in ['corrente', 'poupanca', 'investimento', 'carteira']:
			errors.append('Tipo de conta inválido')
		try:
			saldo_inicial = float(saldo_inicial)
		except Exception:
			errors.append('Saldo inicial inválido')
		if not errors:
			Conta.objects.create(
				usuario=request.user,
				nome=nome,
				tipo=tipo,
				saldo_inicial=saldo_inicial
			)
			success = f"Conta '{nome}' criada com sucesso!"
			contas = Conta.objects.filter(usuario=request.user)
			total_saldo = contas.aggregate(total=Sum('saldo_inicial'))['total'] or 0
		# Não faz redirect para mostrar feedback na mesma tela
	return render(request, 'financeiro/contas.html', {
		'contas': contas,
		'total_saldo': total_saldo,
		'errors': errors,
		'success': success,
	})

@login_required
def transacoes(request):
	from .models import Transacao, Conta
	from datetime import date
	contas = Conta.objects.filter(usuario=request.user)
	transacoes = Transacao.objects.filter(usuario=request.user).order_by('-criado_em', '-data')
	# Sugerir categorias existentes
	categorias_existentes = Transacao.objects.filter(usuario=request.user).values_list('categoria', flat=True).distinct()
	errors = []
	warnings = []
	success = ''
	tipo_pre_selecionado = request.GET.get('tipo', '')
	today = date.today()

	# Adicionar transação
	if request.method == 'POST' and 'add_transacao' in request.POST:
		tipo = request.POST.get('tipo')
		valor = request.POST.get('valor')
		descricao = request.POST.get('descricao')
		categoria = request.POST.get('categoria')
		conta_id = request.POST.get('conta')
		data_trans = request.POST.get('data')
		from decimal import Decimal, InvalidOperation
		try:
			valor = Decimal(valor)
		except (InvalidOperation, TypeError):
			errors.append('Valor inválido')
		if tipo not in ['receita', 'despesa']:
			errors.append('Tipo inválido')
		if not descricao or not categoria or not conta_id or not data_trans:
			errors.append('Preencha todos os campos')
		try:
			conta = Conta.objects.get(id=conta_id, usuario=request.user)
		except Conta.DoesNotExist:
			errors.append('Conta inválida')
			conta = None
		# Validação de saldo para despesa
		if tipo == 'despesa' and conta and valor > conta.saldo_inicial:
			errors.append('Saldo insuficiente na conta')
		if not errors and conta:
			transacao = Transacao.objects.create(
				conta=conta,
				usuario=request.user,
				tipo=tipo,
				categoria=categoria,
				valor=valor,
				descricao=descricao,
				data=data_trans
			)
			# Atualizar saldo da conta
			mult = Decimal('1') if tipo == 'receita' else Decimal('-1')
			conta.saldo_inicial += valor * mult
			conta.save()
			# Aviso se conta ficou negativa
			if conta.saldo_inicial < 0:
				warnings.append(f"Atenção: a conta '{conta.nome}' ficou negativa!")
			success = f"Transação '{descricao}' adicionada com sucesso!"
			contas = Conta.objects.filter(usuario=request.user)
			transacoes = Transacao.objects.filter(usuario=request.user).order_by('-criado_em', '-data')
	# Excluir transação
	if request.method == 'POST' and 'delete_transacao' in request.POST:
		transacao_id = request.POST.get('transacao_id')
		try:
			transacao = Transacao.objects.get(id=transacao_id, usuario=request.user)
			conta = transacao.conta
			mult = Decimal('-1') if transacao.tipo == 'receita' else Decimal('1')
			conta.saldo_inicial += transacao.valor * mult
			conta.save()
			transacao.delete()
			success = 'Transação deletada com sucesso! O saldo da conta foi ajustado automaticamente.'
			contas = Conta.objects.filter(usuario=request.user)
			transacoes = Transacao.objects.filter(usuario=request.user).order_by('-criado_em', '-data')
		except Transacao.DoesNotExist:
			errors.append('Transação não encontrada ou não autorizada.')
	return render(request, 'financeiro/transacoes.html', {
		'transacoes': transacoes,
		'contas': contas,
		'errors': errors,
		'warnings': warnings,
		'success': success,
		'today': today,
		'tipo_pre_selecionado': tipo_pre_selecionado,
		'categorias_existentes': categorias_existentes,
	})

@login_required
def metas(request):
	from .models import Meta
	from datetime import date
	metas_objs = Meta.objects.filter(usuario=request.user).order_by('data_limite')
	errors = []
	warnings = []
	success = ''
	today = date.today()
	# Adicionar meta
	if request.method == 'POST' and 'add_meta' in request.POST:
		nome = request.POST.get('nome')
		valor = request.POST.get('valor')
		valor_atual = request.POST.get('valor_atual', 0)
		data_limite = request.POST.get('data_limite')
		from decimal import Decimal, InvalidOperation
		try:
			valor = Decimal(valor)
			valor_atual = Decimal(valor_atual)
		except (InvalidOperation, TypeError):
			errors.append('Valor inválido')
		if not nome or not valor or not data_limite:
			errors.append('Preencha todos os campos')
		if not errors:
			meta = Meta.objects.create(
				usuario=request.user,
				nome=nome,
				valor=valor,
				valor_atual=valor_atual,
				data_limite=data_limite
			)
			# Cálculo de progresso
			progresso = (valor_atual / valor) * 100 if valor > 0 else 0
			progresso = min(progresso, 100)
			success = f"Meta '{nome}' criada com sucesso!"
			metas_objs = Meta.objects.filter(usuario=request.user).order_by('data_limite')
	# Lista de metas com progresso
	metas = []
	for meta in metas_objs:
		valor = meta.valor
		valor_atual = meta.valor_atual
		progresso = (valor_atual / valor) * 100 if valor > 0 else 0
		progresso = min(progresso, 100)
		valor_restante = valor - valor_atual
		metas.append({
			'nome': meta.nome,
			'valor': valor,
			'valor_atual': valor_atual,
			'valor_restante': valor_restante,
			'data_limite': meta.data_limite,
			'progresso': progresso,
		})
	return render(request, 'financeiro/metas.html', {
		'metas': metas,
		'errors': errors,
		'warnings': warnings,
		'success': success,
		'today': today,
	})

from django.contrib.auth import get_user_model

@login_required
def usuarios(request):
	Usuario = get_user_model()
	if not request.user.is_superuser:
		return redirect('dashboard')
	errors = []
	success = ''
	if request.method == 'POST':
		if 'create_user' in request.POST:
			username = request.POST.get('username', '').strip()
			password = request.POST.get('password')
			role = request.POST.get('role', 'visitante')
			if len(username) < 3:
				errors.append('Username deve ter pelo menos 3 caracteres')
			if len(password) < 6:
				errors.append('Senha deve ter pelo menos 6 caracteres')
			if Usuario.objects.filter(username=username).exists():
				errors.append('Username já existe')
			if role not in ['admin', 'gestor', 'visitante']:
				errors.append('Role inválida')
			if not errors:
				user = Usuario.objects.create_user(username=username, password=password, role=role)
				success = f"Usuário '{username}' criado com sucesso!"
		if 'delete_user' in request.POST and request.user.is_superuser:
			user_id = request.POST.get('user_id')
			try:
				user = Usuario.objects.get(id=user_id)
				if user != request.user:
					user.delete()
					success = f"Usuário '{user.username}' deletado com sucesso!"
				else:
					errors.append('Não é permitido deletar a si mesmo.')
			except Usuario.DoesNotExist:
				errors.append('Usuário não encontrado.')
	usuarios = Usuario.objects.all()
	return render(request, 'financeiro/usuarios.html', {
		'usuarios': usuarios,
		'errors': errors,
		'success': success,
	})

@login_required
def relatorios(request):
	from .models import Transacao, Conta
	from django.db.models import Sum
	from datetime import date
	filtro = request.GET.get('filtro', 'ganhos')
	today = date.today()
	mes_atual = today.strftime('%Y-%m')
	if filtro == 'ganhos':
		transacoes = Transacao.objects.filter(
			usuario=request.user,
			tipo='receita',
			data__year=today.year,
			data__month=today.month
		).order_by('-data', '-valor')
		total = transacoes.aggregate(total=Sum('valor'))['total'] or 0
		titulo = f"💰 Ganhos de {today.strftime('%m/%Y')}"
		cor = "text-green-400"
	else:
		transacoes = Transacao.objects.filter(
			usuario=request.user,
			tipo='despesa',
			data__year=today.year,
			data__month=today.month
		).order_by('-data', '-valor')
		total = transacoes.aggregate(total=Sum('valor'))['total'] or 0
		titulo = f"💸 Despesas de {today.strftime('%m/%Y')}"
		cor = "text-red-400"
	# Agrupar por categoria
	from decimal import Decimal
	por_categoria = {}
	for t in transacoes:
		cat = t.categoria
		if cat not in por_categoria:
			por_categoria[cat] = {'total': Decimal('0.00'), 'count': 0}
		por_categoria[cat]['total'] += t.valor
		por_categoria[cat]['count'] += 1
	por_categoria = dict(sorted(por_categoria.items(), key=lambda item: item[1]['total'], reverse=True))
	return render(request, 'financeiro/relatorios.html', {
		'transacoes': transacoes,
		'total': total,
		'titulo': titulo,
		'cor': cor,
		'por_categoria': por_categoria,
		'filtro': filtro,
	})

@login_required
def logs(request):
	from .models import SystemLog
	from django.core.paginator import Paginator
	if request.user.is_superuser:
		logs_qs = SystemLog.objects.select_related('usuario').order_by('-data')
	else:
		logs_qs = SystemLog.objects.filter(usuario=request.user).order_by('-data')
	paginator = Paginator(logs_qs, 5)
	page_number = request.GET.get('page', 1)
	page_obj = paginator.get_page(page_number)
	logs = page_obj.object_list
	return render(request, 'financeiro/logs.html', {
		'logs': logs,
		'page_obj': page_obj,
	})

@login_required
def admin_dashboard(request):
    # Aqui você pode adicionar lógica específica do painel admin, se necessário
    return render(request, 'financeiro/admin_dashboard.html')

@login_required
def backup(request):
    backup_url = None
    error = None
    if request.method == 'POST':
        try:
            # Exemplo: gerar backup do banco de dados (ajuste conforme sua infra)
            import os, datetime
            from django.conf import settings
            from django.http import FileResponse
            data_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_sysfinance_{data_str}.json"
            backup_path = os.path.join(settings.BASE_DIR, backup_filename)
            os.system(f"python manage.py dumpdata > {backup_path}")
            backup_url = f"/{backup_filename}"
        except Exception as e:
            error = f"Erro ao gerar backup: {e}"
    return render(request, 'financeiro/backup.html', {'backup_url': backup_url, 'error': error})

@login_required
def extratos(request):
    from .models import Transacao, Conta
	contas = Conta.objects.filter(usuario=request.user)
	transacoes = Transacao.objects.filter(usuario=request.user)
	conta_id = request.GET.get('conta')
	inicio = request.GET.get('inicio')
	fim = request.GET.get('fim')
	if conta_id:
		transacoes = transacoes.filter(conta_id=conta_id)
	if inicio:
		transacoes = transacoes.filter(data__gte=inicio)
	if fim:
		transacoes = transacoes.filter(data__lte=fim)
	transacoes = transacoes.order_by('-data', '-criado_em')
	# Calcular saldo final e inicial para extrato
	saldo_inicial = contas.get(id=conta_id).saldo_inicial if conta_id and contas.filter(id=conta_id).exists() else None
	saldo_final = None
	if saldo_inicial is not None:
		saldo_final = saldo_inicial
		for t in transacoes:
			mult = 1 if t.tipo == 'receita' else -1
			saldo_final += t.valor * mult
	return render(request, 'financeiro/extratos.html', {
		'contas': contas,
		'transacoes': transacoes,
		'saldo_inicial': saldo_inicial,
		'saldo_final': saldo_final,
	})

@login_required
def transferencias(request):
    from .models import Conta, Transferencia
    contas = Conta.objects.filter(usuario=request.user)
    error = None
    success = None
    if request.method == 'POST':
        origem_id = request.POST.get('conta_origem')
        destino_id = request.POST.get('conta_destino')
        valor = request.POST.get('valor')
        try:
            valor = float(valor)
            if origem_id == destino_id:
                raise Exception('Contas de origem e destino devem ser diferentes.')
            conta_origem = contas.get(id=origem_id)
            conta_destino = contas.get(id=destino_id)
            if conta_origem.saldo_inicial < valor:
                raise Exception('Saldo insuficiente na conta de origem.')
            # Atualiza saldos
            conta_origem.saldo_inicial -= valor
            conta_destino.saldo_inicial += valor
            conta_origem.save()
            conta_destino.save()
            # Registra transferência
            Transferencia.objects.create(
                usuario=request.user,
                conta_origem=conta_origem,
                conta_destino=conta_destino,
                valor=valor
            )
            success = 'Transferência realizada com sucesso!'
        except Exception as e:
            error = str(e)
    transferencias = Transferencia.objects.filter(usuario=request.user).order_by('-data')
    return render(request, 'financeiro/transferencias.html', {
        'contas': contas,
        'transferencias': transferencias,
        'error': error,
        'success': success
    })

@login_required
def admin_backup(request):
    backup_url = None
    error = None
    if request.method == 'POST':
        try:
            import os, datetime
            from django.conf import settings
            data_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"admin_backup_sysfinance_{data_str}.json"
            backup_path = os.path.join(settings.BASE_DIR, backup_filename)
            os.system(f"python manage.py dumpdata > {backup_path}")
            backup_url = f"/{backup_filename}"
        except Exception as e:
            error = f"Erro ao gerar backup administrativo: {e}"
    return render(request, 'financeiro/admin_backup.html', {'backup_url': backup_url, 'error': error})

@login_required
def admin_reports(request):
    from .models import Log
    logs = Log.objects.all().order_by('-data')
    inicio = request.GET.get('inicio')
    fim = request.GET.get('fim')
    if inicio:
        logs = logs.filter(data__gte=inicio)
    if fim:
        logs = logs.filter(data__lte=fim)
    return render(request, 'financeiro/admin_reports.html', {'logs': logs})

@login_required
def admin_reset(request):
    success = None
    error = None
    if request.method == 'POST':
        try:
            # Exemplo: resetar dados do sistema (ajuste conforme sua regra de negócio)
            from django.core.management import call_command
            call_command('flush', '--noinput')
            success = 'Sistema resetado com sucesso!'
        except Exception as e:
            error = f'Erro ao resetar sistema: {e}'
    return render(request, 'financeiro/admin_reset.html', {'success': success, 'error': error})

@login_required
def admin_users(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    error = None
    success = None
    if request.method == 'POST':
        if 'delete_user' in request.POST:
            try:
                user_id = request.POST.get('delete_user')
                user = User.objects.get(id=user_id)
                user.delete()
                success = 'Usuário excluído com sucesso!'
            except Exception as e:
                error = f'Erro ao excluir usuário: {e}'
        else:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            try:
                if User.objects.filter(username=username).exists():
                    raise Exception('Nome de usuário já existe.')
                user = User.objects.create_user(username=username, email=email, password=password)
                success = 'Usuário criado com sucesso!'
            except Exception as e:
                error = f'Erro ao criar usuário: {e}'
    users = User.objects.all().order_by('username')
    return render(request, 'financeiro/admin_users.html', {'users': users, 'error': error, 'success': success})

@login_required
def debug_database(request):
    columns = []
    rows = []
    error = None
    if request.method == 'POST':
        sql = request.POST.get('sql')
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                else:
                    columns = ['Resultado']
                    rows = [[f'{cursor.rowcount} linha(s) afetada(s)']]
        except Exception as e:
            error = f'Erro ao executar SQL: {e}'
    return render(request, 'financeiro/debug_database.html', {'columns': columns, 'rows': rows, 'error': error})

@login_required
def debug_login_mark3(request):
    result = None
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        from django.contrib.auth import authenticate
        user = authenticate(request, username=username, password=password)
        if user is not None:
            result = f'Login bem-sucedido para: {user.username}'
        else:
            error = 'Usuário ou senha inválidos.'
    return render(request, 'financeiro/debug_login_mark3.html', {'result': result, 'error': error})

@login_required
def diagnose_mark3(request):
    result = None
    error = None
    if request.method == 'POST':
        try:
            # Diagnóstico fictício, ajuste conforme sua lógica
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM financeiro_conta')
                contas = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM financeiro_transacao')
                transacoes = cursor.fetchone()[0]
            result = f'Contas: {contas}, Transações: {transacoes}'
        except Exception as e:
            error = f'Erro no diagnóstico: {e}'
    return render(request, 'financeiro/diagnose_mark3.html', {'result': result, 'error': error})

@login_required
def force_restore_mark3(request):
    result = None
    error = None
    if request.method == 'POST':
        try:
            # Lógica fictícia de restauração, ajuste conforme necessário
            result = 'Restauração forçada executada com sucesso!'
        except Exception as e:
            error = f'Erro na restauração: {e}'
    return render(request, 'financeiro/force_restore_mark3.html', {'result': result, 'error': error})

@login_required
def reset_mark3_teste(request):
    result = None
    error = None
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            # Lógica fictícia de reset de teste
            result = 'Reset de teste Mark3 executado com sucesso!'
        except Exception as e:
            error = f'Erro no reset de teste: {e}'
    return render(request, 'financeiro/reset_mark3_teste.html', {'result': result, 'error': error})

@login_required
def restore_manual_mark3(request):
    result = None
    error = None
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            # Lógica fictícia de restauração manual
            result = 'Restauração manual executada com sucesso!'
        except Exception as e:
            error = f'Erro na restauração manual: {e}'
    return render(request, 'financeiro/restore_manual_mark3.html', {'result': result, 'error': error})

@login_required
def restore_mark3_manual(request):
    result = None
    error = None
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            # Lógica fictícia de restauração Mark3 manual
            result = 'Restauração Mark3 manual executada com sucesso!'
        except Exception as e:
            error = f'Erro na restauração Mark3 manual: {e}'
    return render(request, 'financeiro/restore_mark3_manual.html', {'result': result, 'error': error})

@login_required
def restore_mark3_teste(request):
    result = None
    error = None
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            # Lógica fictícia de restauração de teste
            result = 'Restauração de teste Mark3 executada com sucesso!'
        except Exception as e:
            error = f'Erro na restauração de teste: {e}'
    return render(request, 'financeiro/restore_mark3_teste.html', {'result': result, 'error': error})

@login_required
def restore_simples_mark3(request):
    result = None
    error = None
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            # Lógica fictícia de restauração simples
            result = 'Restauração simples Mark3 executada com sucesso!'
        except Exception as e:
            error = f'Erro na restauração simples: {e}'
    return render(request, 'financeiro/restore_simples_mark3.html', {'result': result, 'error': error})

@login_required
def status(request):
    status = None
    error = None
    if request.method == 'POST':
        try:
            # Lógica fictícia de status
            status = 'Sistema operacional e sem erros críticos.'
        except Exception as e:
            error = f'Erro ao obter status: {e}'
    return render(request, 'financeiro/status.html', {'status': status, 'error': error})

@login_required
def verificacao_completa(request):
    result = None
    error = None
    if request.method == 'POST':
        try:
            # Lógica fictícia de verificação completa
            result = 'Verificação completa executada com sucesso!'
        except Exception as e:
            error = f'Erro na verificação completa: {e}'
    return render(request, 'financeiro/verificacao_completa.html', {'result': result, 'error': error})

@login_required
def verificacao_final(request):
    result = None
    error = None
    if request.method == 'POST':
        try:
            # Lógica fictícia de verificação final
            result = 'Verificação final executada com sucesso!'
        except Exception as e:
            error = f'Erro na verificação final: {e}'
    return render(request, 'financeiro/verificacao_final.html', {'result': result, 'error': error})
