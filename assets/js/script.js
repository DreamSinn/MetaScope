// Animação para os cards de métricas
document.addEventListener('DOMContentLoaded', function() {
    const metricCards = document.querySelectorAll('.stMetric');
    
    metricCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `all 0.5s ease ${index * 0.1}s`;
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100);
    });
    
    // Tooltip personalizado
    const infoIcons = document.querySelectorAll('.info-icon');
    infoIcons.forEach(icon => {
        icon.addEventListener('mouseenter', function() {
            const tooltip = this.nextElementSibling;
            tooltip.style.display = 'block';
        });
        
        icon.addEventListener('mouseleave', function() {
            const tooltip = this.nextElementSibling;
            tooltip.style.display = 'none';
        });
    });
});

// Função para atualizar gráficos dinamicamente
function updateCharts(data) {
    // Esta função seria usada em uma implementação real com dados dinâmicos
    console.log('Dados atualizados:', data);
}