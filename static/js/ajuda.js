/*
 * HemoFlow 2.0 — aba Ajuda (doador, banco de sangue, parceiro e admin)
 * Perguntas frequentes de cada perfil + formulário "Fale com a equipe HemoFlow"
 * (usa a rota /api/support, que manda e-mail para a equipe e devolve um protocolo).
 */
import { api, $, esc, aviso, aoEnviar } from "./nucleo.js";

const PERGUNTAS = {
  DOADOR: [
    ["Como agendo minha doação?", "Toque em <b>Agendar</b> no menu de baixo, escolha o local, o dia e o horário e confirme. O banco de sangue recebe o aviso na hora e você recebe um código de 6 dígitos."],
    ["O que é o código de 6 dígitos?", "É o seu comprovante de agendamento. Mostre no balcão do banco de sangue: depois da coleta, a equipe digita o código e a sua doação fica <b>verificada</b> no app."],
    ["Não vou poder ir. E agora?", "Na tela <b>Início</b>, toque em <b>Não vou poder ir · cancelar</b>. A vaga fica livre para outra pessoa e o banco é avisado. Você pode marcar outro dia depois."],
    ["Quando posso doar de novo?", "Homens: a cada 60 dias, até 4 vezes por ano. Mulheres: a cada 90 dias, até 3 vezes por ano. O app calcula sozinho e mostra a data na tela Início. A decisão final é sempre da triagem."],
    ["O que significam as cores do termômetro?", "<b>Vermelho (crítico)</b>: falta muito sangue desse tipo. <b>Laranja (atenção)</b>: o estoque está baixando. <b>Verde (normal)</b>: estoque bom. Quem informa é o próprio banco de sangue."],
    ["Quem pode doar?", "Pessoas de 16 a 69 anos, com mais de 50 kg e boa saúde. Quem tem 16 ou 17 anos precisa da autorização do responsável. Leve documento oficial com foto, não vá em jejum e evite comida gordurosa 3 horas antes."],
    ["Como ganho os cupons de Vantagens?", "Os cupons ficam liberados por 6 meses depois de uma doação <b>verificada</b> pelo banco de sangue. Gere o cupom no app e mostre o código no parceiro. Cada cupom vale uma vez."],
    ["Doei em um hemocentro público. Conta?", "Sim. Vá em <b>Perfil › Histórico</b> e registre a doação. Ela aparece como “declarada”: conta para o intervalo entre doações, mas não libera cupons."],
    ["Como deixo a letra maior ou o app escuro?", "Em <b>Perfil › Letra, contraste e tema</b> você escolhe letra maior, alto contraste, tema escuro e menos animações."],
    ["Esqueci minha senha.", "Na tela de entrada, toque em <b>Esqueci minha senha</b> ou entre com <b>Código por e-mail</b>: mandamos um código de 6 dígitos para o seu e-mail."],
    ["Não quero mais receber convocações.", "Em <b>Perfil › Meus dados e avisos</b>, desmarque a opção de convocações. Você continua podendo agendar quando quiser."],
    ["Como excluo minha conta?", "Em <b>Perfil › Meus dados e avisos</b>, no fim da página, toque em <b>Excluir minha conta</b>, digite sua senha e escreva EXCLUIR. Seus dados pessoais são apagados na hora; fica só o histórico de doações sem identificar você."],
  ],
  BANCO: [
    ["Como atualizo o estoque?", "Em <b>Estoque</b>, use <b>+</b> e <b>−</b> para entradas e saídas de uma bolsa. Para várias bolsas ou para corrigir a contagem, toque no termômetro do tipo e use <b>Ajuste (contagem)</b>."],
    ["Como funcionam as cores do termômetro?", "Cada tipo tem dois limites que vocês definem: até o <b>crítico</b> fica vermelho, até o de <b>atenção</b> fica laranja e acima fica verde. Toque no termômetro para mudar os limites. O doador vê só a cor, nunca a quantidade."],
    ["Como convoco doadores?", "Em <b>Convocar doadores</b>, escolha o tipo. O HemoFlow mostra quantas bolsas faltam, quantos doadores aptos existem na região e sugere quantos chamar (contando que cerca de metade comparece). Revise a mensagem e envie."],
    ["Por que a sugestão está zerada?", "Ou o estoque não precisa de convocação, ou não há doadores aptos do tipo na cidade, ou não há horários livres. Nesse último caso, abra horários na <b>Agenda</b>."],
    ["Como abro horários de doação?", "Em <b>Agenda › Abrir horários</b>, escolha o dia, os horários separados por vírgula (ex.: 08:00, 09:00) e quantos doadores cabem em cada horário."],
    ["Como sei quem vai doar?", "O sino avisa a cada novo agendamento ou cancelamento. Em <b>Agenda</b> aparecem os horários do dia com o nome, o tipo e o código de cada doador."],
    ["Como confirmo uma doação?", "Depois da triagem e da coleta, abra <b>Confirmar doação</b> e digite o código de 6 dígitos que o doador mostra. A doação fica verificada e libera os benefícios do doador."],
    ["O doador não apareceu.", "Em <b>Agenda</b>, toque em <b>Marcar falta</b> ao lado do nome. Isso entra no cálculo de comparecimento dos <b>Resultados</b>."],
    ["Uma informação aparece como “editado pelo admin”.", "A equipe HemoFlow pode corrigir dados quando vocês pedem. Toda alteração fica registrada na auditoria."],
  ],
  PARCEIRO: [
    ["Como valido um cupom?", "Peça ao cliente o código do app (ex.: DOA-7KJ2), digite em <b>Validar cupom</b> e confirme. O uso fica registrado e o mesmo cupom não pode ser usado de novo."],
    ["Por que minha oferta não aparece no app?", "Toda oferta nova passa pela aprovação da equipe HemoFlow. Enquanto isso, ela aparece como “Aguardando aprovação” em <b>Ofertas</b>."],
    ["Quem pode usar as ofertas?", "Só doadores com doação verificada pelo banco de sangue nos últimos 6 meses."],
    ["Como funciona o código dos alunos?", "Cursinhos, pré-Enem e faculdades recebem um código. O aluno digita no app e vocês veem apenas números gerais da turma, a partir de 5 alunos. Nenhum nome ou dado de saúde é mostrado."],
  ],
  ADMINISTRADOR: [
    ["Como cadastro um banco de sangue ou parceiro?", "Em <b>Bancos de sangue</b> ou <b>Parceiros</b>, use <b>+ Novo</b>. Depois crie a conta de acesso deles em <b>Contas de acesso</b>."],
    ["Como vejo o sistema como um banco, parceiro ou doador?", "Use <b>Entrar como</b> na linha do cadastro. Uma faixa escura avisa que você está nesse modo; toque em <b>Voltar ao painel admin</b> para sair. Tudo fica registrado na auditoria."],
    ["Como aprovo ofertas?", "As pendências aparecem no <b>Resumo</b> e em <b>Parceiros › Ofertas</b>."],
  ],
};

export function telaAjuda(papel) {
  const lista = PERGUNTAS[papel] || PERGUNTAS.DOADOR;
  return `
    <section class="cartao"><h2>Perguntas frequentes</h2>
      <div class="faq">${lista.map(([p, r]) => `<details><summary>${esc(p)}</summary><p>${r}</p></details>`).join("")}</div>
    </section>
    <section class="cartao"><h2>Fale com a equipe HemoFlow</h2>
      <p class="muted">Não achou a resposta? Escreva para nós. A resposta chega no seu e-mail.</p>
      <form id="f-ajuda">
        <label>Sobre o quê? <select name="categoria">
          <option>Dúvida</option><option>Problema no sistema</option><option>Acesso e senha</option><option>Sugestão</option><option>Outro</option>
        </select></label>
        <label>Assunto <input name="assunto" maxlength="120" required placeholder="Ex.: não consigo agendar" /></label>
        <label>Mensagem <textarea name="mensagem" maxlength="3000" required placeholder="Conte o que aconteceu, com o máximo de detalhes."></textarea></label>
        <p class="erro hidden" role="alert"></p><p class="sucesso hidden" role="status"></p>
        <button class="btn btn-primario cheio" type="submit">Enviar mensagem</button>
      </form>
    </section>
    ${papel === "DOADOR" ? '<p class="muted pequeno centro">Em caso de mal-estar depois da doação, procure o banco de sangue onde doou ou ligue 192 (SAMU).</p>' : ""}`;
}

export function ligarAjuda(corpo) {
  const form = $("#f-ajuda", corpo);
  if (!form) return;
  aoEnviar(form, async (d) => {
    const r = await api("/api/support", d);
    const ok = form.querySelector(".sucesso");
    ok.textContent = r.mensagem;
    ok.classList.remove("hidden");
    form.assunto.value = "";
    form.mensagem.value = "";
    aviso("Mensagem enviada.");
  });
}
