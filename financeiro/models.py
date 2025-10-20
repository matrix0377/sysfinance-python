from django.db import models
from django.contrib.auth.models import AbstractUser

# Usuários do sistema (roles: admin, gestor, visitante)
class Usuario(AbstractUser):
	ROLE_CHOICES = [
		('admin', 'Administrador'),
		('gestor', 'Gestor'),
		('visitante', 'Visitante'),
	]
	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='visitante')

# Contas financeiras
class Conta(models.Model):
	TIPO_CHOICES = [
		('corrente', 'Corrente'),
		('poupanca', 'Poupança'),
		('investimento', 'Investimento'),
	]
	usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='contas')
	nome = models.CharField(max_length=100)
	tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
	saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	criado_em = models.DateTimeField(auto_now_add=True)

# Transações financeiras
class Transacao(models.Model):
	TIPO_CHOICES = [
		('receita', 'Receita'),
		('despesa', 'Despesa'),
	]
	conta = models.ForeignKey(Conta, on_delete=models.CASCADE, related_name='transacoes')
	usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='transacoes')
	tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
	categoria = models.CharField(max_length=100)
	valor = models.DecimalField(max_digits=12, decimal_places=2)
	descricao = models.CharField(max_length=255, blank=True)
	data = models.DateField()
	criado_em = models.DateTimeField(auto_now_add=True)

# Metas financeiras
class Meta(models.Model):
	usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='metas')
	nome = models.CharField(max_length=100)
	valor = models.DecimalField(max_digits=12, decimal_places=2)
	valor_atual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	data_limite = models.DateField()
	criado_em = models.DateTimeField(auto_now_add=True)

# Transferências entre contas
class Transferencia(models.Model):
	usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='transferencias')
	conta_origem = models.ForeignKey(Conta, on_delete=models.CASCADE, related_name='transferencias_origem')
	conta_destino = models.ForeignKey(Conta, on_delete=models.CASCADE, related_name='transferencias_destino')
	valor = models.DecimalField(max_digits=12, decimal_places=2)
	descricao = models.CharField(max_length=255, blank=True)
	data = models.DateField()
	criado_em = models.DateTimeField(auto_now_add=True)

# Logs de auditoria
class SystemLog(models.Model):
	usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
	acao = models.CharField(max_length=100)
	detalhes = models.TextField(blank=True)
	data = models.DateTimeField(auto_now_add=True)
