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
	if request.method == 'POST':
		nome = request.POST.get('nome')
		tipo = request.POST.get('tipo')
		saldo_inicial = request.POST.get('saldo_inicial', 0)
		if nome and tipo:
			Conta.objects.create(
				usuario=request.user,
				nome=nome,
				tipo=tipo,
				saldo_inicial=saldo_inicial
			)
			return redirect('contas')
	return render(request, 'financeiro/contas.html', {'contas': contas})

@login_required
def transacoes(request):
	from .models import Transacao, Conta
	contas = Conta.objects.filter(usuario=request.user)
	transacoes = Transacao.objects.filter(usuario=request.user).order_by('-data')
	if request.method == 'POST':
		conta_id = request.POST.get('conta')
		tipo = request.POST.get('tipo')
		categoria = request.POST.get('categoria')
		valor = request.POST.get('valor')
		descricao = request.POST.get('descricao')
		data = request.POST.get('data')
		if conta_id and tipo and categoria and valor and data:
			conta = Conta.objects.get(id=conta_id, usuario=request.user)
			Transacao.objects.create(
				conta=conta,
				usuario=request.user,
				tipo=tipo,
				categoria=categoria,
				valor=valor,
				descricao=descricao,
				data=data
			)
			return redirect('transacoes')
	return render(request, 'financeiro/transacoes.html', {'transacoes': transacoes, 'contas': contas})

@login_required
def metas(request):
	from .models import Meta
	metas = Meta.objects.filter(usuario=request.user).order_by('data_limite')
	if request.method == 'POST':
		nome = request.POST.get('nome')
		valor = request.POST.get('valor')
		valor_atual = request.POST.get('valor_atual', 0)
		data_limite = request.POST.get('data_limite')
		if nome and valor and data_limite:
			Meta.objects.create(
				usuario=request.user,
				nome=nome,
				valor=valor,
				valor_atual=valor_atual,
				data_limite=data_limite
			)
			return redirect('metas')
	return render(request, 'financeiro/metas.html', {'metas': metas})

from django.contrib.auth import get_user_model

@login_required
def usuarios(request):
	Usuario = get_user_model()
	if not request.user.is_superuser:
		return redirect('dashboard')
	usuarios = Usuario.objects.all()
	return render(request, 'financeiro/usuarios.html', {'usuarios': usuarios})

@login_required
def relatorios(request):
	from .models import Transacao, Conta
	from django.db.models import Sum
	contas = Conta.objects.filter(usuario=request.user)
	transacoes = Transacao.objects.filter(usuario=request.user)
	total_receitas = transacoes.filter(tipo='receita').aggregate(total=Sum('valor'))['total'] or 0
	total_despesas = transacoes.filter(tipo='despesa').aggregate(total=Sum('valor'))['total'] or 0
	saldo_total = contas.aggregate(total=Sum('saldo_inicial'))['total'] or 0
	return render(request, 'financeiro/relatorios.html', {
		'contas': contas,
		'total_receitas': total_receitas,
		'total_despesas': total_despesas,
		'saldo_total': saldo_total,
	})

@login_required
def logs(request):
	from .models import SystemLog
	logs = SystemLog.objects.all().order_by('-data')[:100]
	return render(request, 'financeiro/logs.html', {'logs': logs})
